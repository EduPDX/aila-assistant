"""Web Agent — pesquisa na internet e leitura de páginas.

Usa o **DuckDuckGo** (endpoint HTML "lite", sem JavaScript) via ``httpx`` —
não precisa de chave de API nem de dependência extra. Duas ferramentas:

    web.search  — pesquisa e devolve os principais resultados (título/link/resumo)
    web.fetch   — baixa uma página e devolve o texto legível (para ler/resumir)

Ambas são **ações de leitura** (não alteram nada no sistema), portanto
funcionam mesmo no modo somente-leitura. A busca não usa chaves nem contas.
"""

from __future__ import annotations

import asyncio
import html as _html
import ipaddress
import re
import socket
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx

from aila.agents.base import BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("web_agent")

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_DDG_HTML = "https://html.duckduckgo.com/html/"

# Cache curto de buscas BEM-SUCEDIDAS: um 7B costuma repetir a MESMA busca várias
# vezes seguidas; sem cache isso bombardeia o DuckDuckGo e ele passa a devolver
# páginas de rate-limit (sem resultados) — o que fazia a busca "falhar" de forma
# intermitente. Com o cache, as repetições viram acerto e o buscador respira.
_SEARCH_CACHE: dict[str, tuple[float, list[dict]]] = {}
_SEARCH_TTL = 300.0   # segundos

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_MULTINL_RE = re.compile(r"\n\s*\n\s*\n+")
_SCRIPT_RE = re.compile(r"<(script|style|noscript|template)\b.*?</\1>", re.S | re.I)
# pareia título (href + texto) com o resumo do MESMO resultado, sem cruzar
# para o próximo título (lookahead negativo).
_RESULT_RE = re.compile(
    r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
    r'(?:(?!result__a").)*?'
    r'result__snippet"[^>]*>(.*?)</a>',
    re.S,
)


def _strip_html(fragment: str) -> str:
    """Remove tags e desescapa entidades de um trecho de HTML."""
    return _html.unescape(_TAG_RE.sub("", fragment)).strip()


def _is_ad(href: str) -> bool:
    """Links patrocinados do DuckDuckGo (não são resultado orgânico)."""
    return any(s in href for s in ("/y.js", "ad_domain", "ad_provider", "ad_type"))


def _real_url(href: str) -> str:
    """Resolve o link real por trás do redirecionamento do DuckDuckGo."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return href


def _unsafe_address(value: str) -> bool:
    """Bloqueia loopback/rede privada/link-local/reservada (anti-SSRF)."""
    try:
        addr = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    return any((addr.is_private, addr.is_loopback, addr.is_link_local,
                addr.is_reserved, addr.is_multicast, addr.is_unspecified))


async def _public_url_error(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return "URL inválida — use http:// ou https://."
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or _unsafe_address(host):
        return "URL bloqueada: web.fetch não acessa localhost ou redes privadas."
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, host, parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        return f"Não foi possível resolver o host: {host}"
    if any(_unsafe_address(info[4][0]) for info in infos):
        return "URL bloqueada: o host resolve para uma rede local/privada."
    return None


class WebAgent(BaseAgent):
    name = "web"
    description = (
        "Pesquisa na internet e lê páginas web (DuckDuckGo, sem chave de API). "
        "Use para obter informação atual, notícias, documentação e fatos que "
        "você não sabe. web.search acha; web.fetch lê a página encontrada."
    )

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="web.search",
                description=(
                    "Pesquisa na web e retorna os principais resultados "
                    "(título, link e resumo). Use para achar informação atual."
                ),
                params=[
                    ToolParam("query", "string", "O que pesquisar"),
                    ToolParam("max_results", "integer", "Máx. de resultados (padrão 5)",
                              required=False),
                ],
                handler=self._search,
                agent=self.name,
            ),
            Tool(
                name="web.fetch",
                description=(
                    "Baixa uma página web (URL http/https) e devolve o texto "
                    "legível dela, para você ler ou resumir."
                ),
                params=[ToolParam("url", "string", "URL http(s) da página")],
                handler=self._fetch,
                agent=self.name,
            ),
        ]

    # ------------------------------------------------------------------ #
    def _offline_block(self) -> ToolResult | None:
        net = self.deps.network
        if net is not None and net.is_offline:
            return ToolResult.error("Pesquisa web indisponível: modo OFFLINE ativo.")
        return None

    async def _search(self, args: dict) -> ToolResult:
        await self.authorize("web.search", args)  # leitura
        if blocked := self._offline_block():
            return blocked
        query = (args.get("query") or "").strip()
        if not query:
            return ToolResult.error("Informe o que pesquisar (query vazia).")
        try:
            n = max(1, min(10, int(args.get("max_results") or 5)))
        except (TypeError, ValueError):
            n = 5
        import time as _time

        chave = f"{query.lower()}|{n}"
        cached = _SEARCH_CACHE.get(chave)
        if cached and (_time.time() - cached[0]) < _SEARCH_TTL:
            results = cached[1]                      # repetição → cache (sem bater no DDG)
        else:
            try:
                results = await self._ddg_search(query, n)
            except httpx.HTTPError as exc:
                return ToolResult.error(
                    f"A busca falhou (rede: {exc}). Responda com o que você já sabe "
                    "sobre isso; NÃO repita a busca.")
            except Exception:  # noqa: BLE001
                log.exception("erro na busca web")
                return ToolResult.error(
                    "A busca falhou. Responda com o que você já sabe; NÃO repita a busca.")
            if results:
                _SEARCH_CACHE[chave] = (_time.time(), results)
        if not results:
            # provável rate-limit do buscador → NÃO insista (senão piora): responda
            # do próprio conhecimento. Isto quebra o ciclo de buscas repetidas.
            return ToolResult.error(
                f"A busca por '{query}' não retornou agora (o buscador limitou as "
                "consultas repetidas). Responda com o que você já sabe sobre isso, "
                "sem pesquisar de novo.")
        lines = [
            f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}"
            for i, r in enumerate(results, 1)
        ]
        return ToolResult.success("\n".join(lines), results=results, query=query)

    async def _ddg_search(self, query: str, n: int) -> list[dict]:
        async with httpx.AsyncClient(
            timeout=15, headers={"User-Agent": _UA}, follow_redirects=True
        ) as client:
            resp = await client.post(_DDG_HTML, data={"q": query, "kl": "br-pt"})
            resp.raise_for_status()
            page = resp.text
        return self._parse_results(page, n)

    @staticmethod
    def _parse_results(page: str, n: int) -> list[dict]:
        """Extrai (título, url, resumo) dos resultados ORGÂNICOS do DuckDuckGo,
        descartando anúncios e links internos de redirecionamento."""
        results: list[dict] = []
        for href, title_html, snippet_html in _RESULT_RE.findall(page):
            if _is_ad(href):
                continue
            url = _real_url(href)
            if "duckduckgo.com" in urlparse(url).netloc:  # ainda é link do DDG: pula
                continue
            results.append({
                "title": _strip_html(title_html) or "(sem título)",
                "url": url,
                "snippet": _strip_html(snippet_html),
            })
            if len(results) >= n:
                break
        return results

    # ------------------------------------------------------------------ #
    async def _fetch(self, args: dict) -> ToolResult:
        await self.authorize("web.page.get", args)  # leitura
        if blocked := self._offline_block():
            return blocked
        url = (args.get("url") or "").strip()
        if error := await _public_url_error(url):
            return ToolResult.error(error)
        try:
            async with httpx.AsyncClient(
                timeout=20, headers={"User-Agent": _UA}, follow_redirects=False
            ) as client:
                current = url
                for _ in range(6):
                    if error := await _public_url_error(current):
                        return ToolResult.error(error)
                    resp = await client.get(current)
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            return ToolResult.error("Redirecionamento sem destino.")
                        current = urljoin(str(resp.url), location)
                        continue
                    break
                else:
                    return ToolResult.error("Muitos redirecionamentos (>5).")
                resp.raise_for_status()
                ctype = resp.headers.get("content-type", "")
                if "html" not in ctype and "text" not in ctype and ctype:
                    return ToolResult.error(f"Conteúdo não textual ({ctype}).")
                text = self._html_to_text(resp.text)
                final_url = str(resp.url)
        except httpx.HTTPError as exc:
            return ToolResult.error(f"Falha ao baixar a página: {exc}")
        if not text:
            return ToolResult.error("A página não tem texto extraível.")
        clipped = text[:8000]
        suffix = "\n\n[…texto truncado]" if len(text) > 8000 else ""
        return ToolResult.success(clipped + suffix, url=final_url, chars=len(text))

    @staticmethod
    def _html_to_text(page: str) -> str:
        page = _SCRIPT_RE.sub(" ", page)          # tira script/style/etc.
        page = re.sub(r"<br\s*/?>", "\n", page, flags=re.I)
        page = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", page, flags=re.I)
        text = _html.unescape(_TAG_RE.sub("", page))
        text = _WS_RE.sub(" ", text)
        text = _MULTINL_RE.sub("\n\n", text)
        return "\n".join(line.strip() for line in text.splitlines()).strip()
