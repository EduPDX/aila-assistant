"""File Agent — criar, editar, organizar e pesquisar arquivos.

Todas as operações são confinadas ao sandbox e passam pelo controle de
permissões. Escritas/exclusões respeitam o modo somente-leitura e a
confirmação de ações destrutivas.
"""

from __future__ import annotations

import fnmatch
import re
import shutil

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("file_agent")

MAX_READ_BYTES = 200_000


class FileAgent(BaseAgent):
    name = "file"
    description = (
        "Manipula arquivos dentro do workspace: ler, escrever, listar, "
        "pesquisar por nome/conteúdo, mover e apagar."
    )

    def __init__(self, deps: AgentDeps) -> None:
        super().__init__(deps)
        self.sandbox = deps.sandbox

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="file.read",
                description="Lê o conteúdo de um arquivo de texto.",
                params=[ToolParam("path", "string", "Caminho relativo ao workspace")],
                handler=self._read,
                agent=self.name,
            ),
            Tool(
                name="file.write",
                description="Cria ou sobrescreve um arquivo de texto.",
                params=[
                    ToolParam("path", "string", "Caminho relativo ao workspace"),
                    ToolParam("content", "string", "Conteúdo a escrever"),
                ],
                handler=self._write,
                agent=self.name,
            ),
            Tool(
                name="file.edit",
                description=(
                    "Edita um arquivo IN-PLACE: substitui old_string por new_string. "
                    "old_string deve ser único no arquivo (se aparecer múltiplas vezes, "
                    "a edit falha). Use para mudanças cirúrgicas sem reescrever o arquivo inteiro."
                ),
                params=[
                    ToolParam("path", "string", "Caminho relativo ao workspace"),
                    ToolParam("old_string", "string", "Texto exato a substituir (deve ser único)"),
                    ToolParam("new_string", "string", "Novo texto (pode ser vazio para deletar)"),
                ],
                handler=self._edit,
                agent=self.name,
            ),
            Tool(
                name="file.list",
                description="Lista arquivos e pastas de um diretório.",
                params=[
                    ToolParam("path", "string", "Diretório (vazio = raiz)", required=False)
                ],
                handler=self._list,
                agent=self.name,
            ),
            Tool(
                name="file.search",
                description="Procura arquivos por trecho no nome ou no conteúdo.",
                params=[
                    ToolParam("query", "string", "Texto a procurar"),
                    ToolParam(
                        "in_content", "boolean", "Buscar no conteúdo?", required=False
                    ),
                ],
                handler=self._search,
                agent=self.name,
            ),
            Tool(
                name="file.grep",
                description=(
                    "Busca por REGEX no conteúdo de arquivos (como ripgrep). "
                    "Retorna linhas com número e nome do arquivo. Muito mais poderoso que file.search."
                ),
                params=[
                    ToolParam("pattern", "string", "Regex (Python re) para buscar"),
                    ToolParam("path", "string", "Diretório base (vazio = workspace)", required=False),
                    ToolParam("include", "string", "Glob de arquivos (ex: *.py)", required=False),
                ],
                handler=self._grep,
                agent=self.name,
            ),
            Tool(
                name="file.glob",
                description=(
                    "Busca arquivos por padrão (glob patterns). "
                    "Suporta ** para recursivo. Ex: **/*.py, src/**/*.ts"
                ),
                params=[
                    ToolParam("pattern", "string", "Glob pattern (ex: **/*.py)"),
                    ToolParam("path", "string", "Diretório base (vazio = workspace)", required=False),
                ],
                handler=self._glob,
                agent=self.name,
            ),
            Tool(
                name="file.delete",
                description="Apaga um arquivo (ação destrutiva, exige confirmação).",
                params=[ToolParam("path", "string", "Caminho relativo ao workspace")],
                handler=self._delete,
                agent=self.name,
            ),
            Tool(
                name="file.move",
                description="Move ou renomeia um arquivo/pasta.",
                params=[
                    ToolParam("src", "string", "Origem"),
                    ToolParam("dst", "string", "Destino"),
                ],
                handler=self._move,
                agent=self.name,
            ),
        ]

    # ------------------------------------------------------------------ #
    async def _read(self, args: dict) -> ToolResult:
        await self.authorize("file.read", args)
        path = self.sandbox.resolve(args["path"], read=True)
        if not path.is_file():
            return ToolResult.error(f"Arquivo não encontrado: {args['path']}")
        data = path.read_bytes()[:MAX_READ_BYTES]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult.error("Arquivo não é texto UTF-8 (use o Binary Agent).")
        return ToolResult.success(text, path=str(path), bytes=len(data))

    async def _write(self, args: dict) -> ToolResult:
        path = self.sandbox.resolve(args["path"])
        action = "file.overwrite" if path.exists() else "file.write"
        await self.authorize(action, args)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(args["content"], encoding="utf-8")
        return ToolResult.success(f"Arquivo salvo: {args['path']}", path=str(path))

    async def _edit(self, args: dict) -> ToolResult:
        """Edita um arquivo in-place: substitui old_string por new_string.
        Se old_string aparecer 0 ou >1 vezes, a edit falha (segurança)."""
        await self.authorize("file.write", args)
        path = self.sandbox.resolve(args["path"])
        if not path.is_file():
            return ToolResult.error(f"Arquivo não encontrado: {args['path']}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult.error("Arquivo não é texto UTF-8.")
        old = args["old_string"]
        new = args.get("new_string", "")
        count = text.count(old)
        if count == 0:
            return ToolResult.error(
                "old_string não encontrada no arquivo. "
                "Verifique o texto exato (incluindo espaços/indentação)."
            )
        if count > 1:
            return ToolResult.error(
                f"old_string aparece {count} vezes no arquivo. "
                "Deve ser única. Forneça mais contexto para torná-la única."
            )
        new_text = text.replace(old, new, 1)
        path.write_text(new_text, encoding="utf-8")
        # Calcula diff para feedback
        old_lines = old.splitlines()
        new_lines = new.splitlines()
        return ToolResult.success(
            f"Editado: {args['path']} ({len(old_lines)}→{len(new_lines)} linhas)",
            path=str(path),
        )

    async def _grep(self, args: dict) -> ToolResult:
        """Busca regex no conteúdo de arquivos (estilo ripgrep)."""
        await self.authorize("file.search", args)
        pattern = args["pattern"]
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return ToolResult.error(f"Regex inválida: {e}")
        include = args.get("include")
        base = self.sandbox.resolve(args.get("path") or ".", read=True)
        if not base.is_dir():
            return ToolResult.error(f"Diretório não encontrado: {args.get('path')}")
        hits: list[str] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if include and not fnmatch.fnmatch(p.name, include):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    rel = p.relative_to(base)
                    hits.append(f"{rel}:{i}: {line.strip()[:120]}")
                    if len(hits) >= 100:
                        break
            if len(hits) >= 100:
                break
        return ToolResult.success("\n".join(hits) or "Nenhum resultado.", count=len(hits))

    async def _glob(self, args: dict) -> ToolResult:
        """Busca arquivos por padrão glob (suporta ** para recursivo)."""
        await self.authorize("file.search", args)
        pattern = args["pattern"]
        base = self.sandbox.resolve(args.get("path") or ".", read=True)
        if not base.is_dir():
            return ToolResult.error(f"Diretório não encontrado: {args.get('path')}")
        matches = sorted(str(p.relative_to(base)) for p in base.rglob("*") if p.is_file() and fnmatch.fnmatch(p.name, pattern))
        if not matches:
            # Tentar glob patterns com ** (rglob já faz isso)
            matches = sorted(str(p.relative_to(base)) for p in base.rglob(pattern) if p.is_file())
        return ToolResult.success("\n".join(matches[:200]) or "Nenhum resultado.", count=len(matches))

    async def _list(self, args: dict) -> ToolResult:
        await self.authorize("file.list", args)
        target = self.sandbox.resolve(args.get("path") or ".", read=True)
        if not target.is_dir():
            return ToolResult.error(f"Não é um diretório: {args.get('path')}")
        entries = []
        for p in sorted(target.iterdir()):
            kind = "dir" if p.is_dir() else "file"
            size = p.stat().st_size if p.is_file() else "-"
            entries.append(f"[{kind}] {p.name} ({size})")
        listing = "\n".join(entries) or "(vazio)"
        return ToolResult.success(listing, count=len(entries))

    async def _search(self, args: dict) -> ToolResult:
        await self.authorize("file.search", args)
        query = args["query"].lower()
        in_content = bool(args.get("in_content"))
        hits: list[str] = []
        for base in self.sandbox.read_bases():   # workspace + pastas anexadas
            for p in base.rglob("*"):
                if not p.is_file():
                    continue
                rel = p.relative_to(base)
                if query in p.name.lower():
                    hits.append(f"{rel} (nome)")
                elif in_content:
                    try:
                        if query in p.read_text(encoding="utf-8", errors="ignore").lower():
                            hits.append(f"{rel} (conteúdo)")
                    except OSError:
                        continue
                if len(hits) >= 100:
                    break
            if len(hits) >= 100:
                break
        return ToolResult.success("\n".join(hits) or "Nenhum resultado.", count=len(hits))

    async def _delete(self, args: dict) -> ToolResult:
        await self.authorize("file.delete", args)
        path = self.sandbox.resolve(args["path"])
        if not path.exists():
            return ToolResult.error(f"Não existe: {args['path']}")
        if path.is_dir():
            # Profundidade máxima: evita deletar árvores inteiras acidentalmente
            depth = sum(1 for _ in path.rglob("*") if _.is_dir())
            if depth > 10:
                return ToolResult.error(
                    f"Diretório muito profundo ({depth} subdiretórios). "
                    "Máximo seguro: 10. Use file.move ou delete manual."
                )
            shutil.rmtree(path)
        else:
            path.unlink()
        return ToolResult.success(f"Apagado: {args['path']}")

    async def _move(self, args: dict) -> ToolResult:
        src = self.sandbox.resolve(args["src"])
        dst = self.sandbox.resolve(args["dst"])
        action = "file.overwrite" if dst.exists() else "file.write"
        await self.authorize(action, args)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return ToolResult.success(f"Movido: {args['src']} -> {args['dst']}")
