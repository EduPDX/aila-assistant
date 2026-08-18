"""Code Agent — geração, análise e correção de código.

Usa um modelo especializado em código (ex.: deepseek-coder) via o mesmo
backend de LLM. Ele não executa código por padrão (isso é uma ação destrutiva
que exigirá o Computer Agent + confirmação numa fase futura).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.config import PROJECT_ROOT, data_path
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("code_agent")


def _qual(node) -> str:
    """qualname legível de um nó de código (sem o prefixo 'code:')."""
    return node.attrs.get("qualname") or node.id.removeprefix("code:")


def _find_python() -> str | None:
    """Acha o interpretador Python do sistema (no .exe, sys.executable é o
    próprio backend — então procuramos no PATH)."""
    for cand in ("python", "py", "python3"):
        exe = shutil.which(cand)
        if exe:
            return exe
    return None


def _venv_python() -> str | None:
    """Python do PROJETO (venv) — necessário p/ rodar os testes (tem as deps).
    Cai para o Python do sistema se não houver venv."""
    for rel in (Path(".venv") / "Scripts" / "python.exe", Path(".venv") / "bin" / "python"):
        cand = PROJECT_ROOT / rel
        if cand.exists():
            return str(cand)
    return _find_python()


def _repo_resolve(rel: str) -> Path | None:
    """Resolve um caminho DENTRO do repositório (bloqueia escapar do PROJECT_ROOT)."""
    root = PROJECT_ROOT.resolve()
    try:
        p = (root / rel).resolve()
    except (OSError, ValueError):
        return None
    return p if str(p).startswith(str(root)) else None


class CodeAgent(BaseAgent):
    name = "code"
    description = (
        "Escreve, explica, revisa, corrige e EXECUTA código. Use code.run para "
        "rodar um código Python e obter a saída real (pede confirmação)."
    )

    def __init__(self, deps: AgentDeps) -> None:
        super().__init__(deps)
        self.code_model = deps.settings.llm.code_model
        self._cg_store = None          # GraphStore do Code Graph (lazy)

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="code.generate",
                description="Gera código a partir de uma descrição.",
                params=[
                    ToolParam("task", "string", "O que o código deve fazer"),
                    ToolParam("language", "string", "Linguagem (ex.: python)", required=False),
                ],
                handler=self._generate,
                agent=self.name,
            ),
            Tool(
                name="code.analyze",
                description="Analisa um trecho de código e aponta problemas.",
                params=[ToolParam("code", "string", "Código a analisar")],
                handler=self._analyze,
                agent=self.name,
            ),
            Tool(
                name="code.fix",
                description="Corrige código a partir de uma mensagem de erro.",
                params=[
                    ToolParam("code", "string", "Código com problema"),
                    ToolParam("error", "string", "Mensagem de erro / comportamento"),
                ],
                handler=self._fix,
                agent=self.name,
            ),
            Tool(
                name="code.run",
                description=(
                    "Executa um código PYTHON e retorna a saída real (stdout/erro). "
                    "Use quando o usuário pedir para RODAR/EXECUTAR um código. "
                    "Não use input() — passe valores fixos no próprio código."
                ),
                params=[ToolParam("code", "string", "Código Python a executar")],
                handler=self._run,
                agent=self.name,
            ),
            Tool(
                name="code.test",
                description="Roda a suíte de testes do projeto (pytest) e devolve o resultado.",
                params=[ToolParam("path", "string", "arquivo/pasta de teste", required=False)],
                handler=self._test,
                agent=self.name,
            ),
            Tool(
                name="code.read_file",
                description="Lê um arquivo do repositório do projeto (caminho relativo à raiz).",
                params=[ToolParam("path", "string", "ex.: aila/core/engine.py")],
                handler=self._read_file,
                agent=self.name,
            ),
            Tool(
                name="code.write_file",
                description=(
                    "ESCREVE um arquivo no repositório (auto-modificação; faz backup .bak). "
                    "Exige autonomia L5 (self-improve)."
                ),
                params=[
                    ToolParam("path", "string", "caminho relativo à raiz do repo"),
                    ToolParam("content", "string", "novo conteúdo completo do arquivo"),
                ],
                handler=self._write_file,
                agent=self.name,
            ),
            # --- Code Graph (Fase 6): mapa estrutural do PRÓPRIO código, read-only ---
            Tool(
                name="code.map",
                description=(
                    "Mapa do código da Aila (repo-map): totais de módulos/classes/funções "
                    "e as funções mais chamadas. Use para se orientar antes de editar. "
                    "refresh=true reconstrói o índice a partir do código atual."
                ),
                params=[ToolParam("refresh", "boolean", "reconstruir o índice", required=False)],
                handler=self._map,
                agent=self.name,
            ),
            Tool(
                name="project.add",
                description=(
                    "Anexa uma PASTA de projeto e constrói o Code Graph dela (aparece na "
                    "aba Projetos). Use quando o usuário pedir para 'salvar o projeto', "
                    "'adicionar aos projetos' ou analisar uma pasta a fundo. Só mapeia "
                    "Python (.py) por enquanto. Passe o caminho da pasta."
                ),
                params=[
                    ToolParam("path", "string", "caminho da pasta do projeto"),
                    ToolParam("name", "string", "nome do projeto (opcional)", required=False),
                ],
                handler=self._project_add,
                agent=self.name,
            ),
            Tool(
                name="project.list",
                description="Lista os projetos já anexados (nome, nós, arestas).",
                params=[],
                handler=self._project_list,
                agent=self.name,
            ),
            Tool(
                name="code.definition",
                description="Onde uma função/classe é definida (módulo, arquivo e linha).",
                params=[ToolParam("name", "string", "nome simples, ex.: authorize")],
                handler=self._definition,
                agent=self.name,
            ),
            Tool(
                name="code.callers",
                description="Quem CHAMA esta função (chamadas resolvidas por nome único).",
                params=[ToolParam("name", "string", "nome da função, ex.: authorize")],
                handler=self._callers,
                agent=self.name,
            ),
            Tool(
                name="code.callees",
                description="O que esta função chama (dependências diretas).",
                params=[ToolParam("name", "string", "nome da função")],
                handler=self._callees,
                agent=self.name,
            ),
            Tool(
                name="code.impact",
                description=(
                    "Análise de IMPACTO: tudo que chama esta função direta ou "
                    "indiretamente (raio de alcance). Use ANTES de alterar algo, "
                    "para saber o que testar."
                ),
                params=[
                    ToolParam("name", "string", "nome da função a alterar"),
                    ToolParam("depth", "integer", "profundidade (default 3)", required=False),
                ],
                handler=self._impact,
                agent=self.name,
            ),
        ]

    # ------------------------------------------------------------------ #
    async def _ask_code_model(self, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return await self.deps.llm.complete(messages, model=self.code_model)

    async def _generate(self, args: dict) -> ToolResult:
        await self.authorize("code.generate", args)
        lang = args.get("language", "python")
        out = await self._ask_code_model(
            f"Você é um engenheiro de software sênior. Escreva código {lang} "
            "limpo, idiomático e comentado. Responda apenas com o código.",
            args["task"],
        )
        return ToolResult.success(out, language=lang)

    async def _analyze(self, args: dict) -> ToolResult:
        await self.authorize("code.analyze", args)
        out = await self._ask_code_model(
            "Você é um revisor de código rigoroso. Aponte bugs, riscos de "
            "segurança e melhorias, em tópicos objetivos.",
            args["code"],
        )
        return ToolResult.success(out)

    async def _fix(self, args: dict) -> ToolResult:
        await self.authorize("code.fix", args)
        out = await self._ask_code_model(
            "Você conserta código. Explique brevemente a causa e devolva a "
            "versão corrigida completa.",
            f"CÓDIGO:\n{args['code']}\n\nERRO:\n{args['error']}",
        )
        return ToolResult.success(out)

    async def _run(self, args: dict) -> ToolResult:
        await self.authorize("code.execute", args)  # destrutiva -> confirmação
        code = (args.get("code") or "").strip()
        if not code:
            return ToolResult.error("Nenhum código para executar.")
        exe = _find_python()
        if not exe:
            return ToolResult.error(
                "Python não encontrado no PATH deste computador. Instale o Python "
                "(python.org) para executar código."
            )
        path = self.deps.sandbox.resolve("_aila_run.py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [exe, str(path)],
                capture_output=True, text=True, timeout=30,
                stdin=subprocess.DEVNULL,  # input() falha rápido em vez de travar
            )
        except subprocess.TimeoutExpired:
            return ToolResult.error("Execução excedeu o tempo limite (30s).")
        finally:
            path.unlink(missing_ok=True)
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return ToolResult.success(out or "(sem saída)", returncode=proc.returncode)

    async def _test(self, args: dict) -> ToolResult:
        await self.authorize("code.test", args)   # roda a suíte (L3; sem confirmar a cada run)
        exe = _venv_python()   # precisa do Python do projeto (com as deps)
        if not exe:
            return ToolResult.error("Python não encontrado (venv/PATH).")
        target = args.get("path") or "tests"
        try:
            proc = subprocess.run(
                [exe, "-m", "pytest", "-q", "--no-header", target],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.error("Testes excederam o tempo limite (180s).")
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        passed = proc.returncode == 0
        tail = out[-1500:]
        return ToolResult.success(
            f"{'✓ PASSOU' if passed else '✗ FALHOU'}\n{tail}",
            passed=passed, returncode=proc.returncode,
        )

    async def _read_file(self, args: dict) -> ToolResult:
        await self.authorize("code.read", args)      # leitura → SAFE
        p = _repo_resolve(args["path"])
        if p is None or not p.is_file():
            return ToolResult.error(f"Arquivo não encontrado no repo: {args['path']}")
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult.error(f"Falha ao ler: {exc}")
        return ToolResult.success(text[:20000], path=args["path"])

    async def _write_file(self, args: dict) -> ToolResult:
        # auto-modificação do próprio código → gate de autonomia L5 (self-improve)
        await self.authorize("code.write", args)
        p = _repo_resolve(args["path"])
        if p is None:
            return ToolResult.error("Caminho fora do repositório.")
        content = args.get("content", "")
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():                                # backup .bak antes de sobrescrever
            try:
                shutil.copyfile(p, p.with_suffix(p.suffix + ".bak"))
            except OSError:
                pass
        try:
            p.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult.error(f"Falha ao escrever: {exc}")
        self.deps.permissions.audit.record(
            "code.write", self.name, {"path": args["path"], "bytes": len(content)},
            "written", allowed=True,
        )
        return ToolResult.success(f"Escrito {args['path']} ({len(content)} bytes; backup .bak).")

    # ------------------------- Code Graph (Fase 6) --------------------- #
    def _graph(self, *, refresh: bool = False):
        """GraphStore do Code Graph a consultar. Se houver um PROJETO ativo (a
        Aila está "trabalhando" nele), usa o grafo DELE; senão, o da própria Aila.
        Construído sob demanda (índice persistente)."""
        from aila.cognition.graph import CodeGraph, GraphStore
        from aila.cognition.graph.projects import get_registry

        reg = get_registry()
        active = reg.active()
        if active:                                   # trabalhando num projeto anexado
            if refresh:
                reg.rebuild(active)
            try:
                return reg.store(active)             # grafo do projeto (já construído)
            except Exception:  # noqa: BLE001 - sem grafo → cai no código da Aila
                pass
        if self._cg_store is None:
            self._cg_store = GraphStore(data_path("code_graph.db"))
        store = self._cg_store
        if refresh or store.counts()["nodes"] == 0:
            CodeGraph(store, PROJECT_ROOT).build(subdir="aila")
        return store

    def _graph_label(self) -> str:
        """De quem é o grafo ativo — 'código da Aila' ou o nome do projeto."""
        from aila.cognition.graph.projects import get_registry

        reg = get_registry()
        a = reg.active()
        meta = reg.get(a) if a else None
        return f"projeto “{meta['name']}”" if meta else "código da Aila"

    def _find(self, store, name: str, types: tuple[str, ...]):
        """Nós por nome simples ou por final do qualname (ex.: BaseAgent.authorize)."""
        nodes = store.nodes_by_label(name, types)
        if not nodes and "." in name:                      # tentativa por qualname
            nodes = [n for n in (store.get_node(f"code:{name}"),) if n]
        return nodes

    async def _map(self, args: dict) -> ToolResult:
        await self.authorize("code.graph.info", args)       # leitura → SAFE/L1
        store = self._graph(refresh=bool(args.get("refresh")))
        c = store.counts()
        bt = c["by_type"]
        top = store.conn.execute(
            "SELECT target, COUNT(*) n FROM kg_edge WHERE relation='calls' "
            "GROUP BY target ORDER BY n DESC LIMIT 15"
        ).fetchall()
        lines = [
            f"Code Graph — {self._graph_label()} — {bt.get('module', 0)} módulos, "
            f"{bt.get('class', 0)} classes, {bt.get('function', 0)} funções, "
            f"{c['edges']} relações (defines/imports/calls).",
            "\nFunções mais chamadas:",
        ]
        for r in top:
            node = store.get_node(r["target"])
            if node:
                lines.append(f"  • {_qual(node)}  ({r['n']} chamadas)")
        return ToolResult.success("\n".join(lines), **c)

    # ------------------------- Projetos -------------------------------- #
    async def _project_add(self, args: dict) -> ToolResult:
        await self.authorize("project.add", args)
        from aila.cognition.graph.projects import get_registry

        p = Path(str(args.get("path", ""))).expanduser()
        if not p.exists() or not p.is_dir():
            return ToolResult.error(f"Não é uma pasta válida: {args.get('path')}")
        try:
            meta = get_registry().add(str(p), args.get("name"))
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Falha ao anexar o projeto: {exc}")
        keep = {k: meta.get(k) for k in ("slug", "name", "nodes", "edges", "files")}
        if not meta.get("nodes"):
            return ToolResult.success(
                f"Projeto '{meta['name']}' anexado, mas o grafo saiu com 0 nós — o "
                f"construtor hoje mapeia só Python (.py). {meta.get('files', 0)} arquivos varridos.",
                **keep)
        return ToolResult.success(
            f"Projeto '{meta['name']}' anexado: {meta['nodes']} nós, {meta['edges']} arestas "
            f"({meta.get('files', 0)} arquivos .py). Aparece na aba Projetos.", **keep)

    async def _project_list(self, args: dict) -> ToolResult:
        from aila.cognition.graph.projects import get_registry

        ps = get_registry().list()
        if not ps:
            return ToolResult.success("Nenhum projeto anexado ainda.")
        lines = [f"• {p['name']} — {p.get('nodes', 0)} nós, {p.get('edges', 0)} arestas" for p in ps]
        return ToolResult.success("Projetos:\n" + "\n".join(lines), count=len(ps))

    async def _definition(self, args: dict) -> ToolResult:
        await self.authorize("code.graph.get", args)
        store = self._graph()
        nodes = self._find(store, args["name"], ("function", "class"))
        if not nodes:
            return ToolResult.error(f"Não achei definição de '{args['name']}' no {self._graph_label()}.")
        out = []
        for n in nodes:
            out.append(f"{_qual(n)} ({n.type}) — {self._owner_file(store, n)}"
                       f":{n.attrs.get('lineno', '?')}")
        return ToolResult.success("\n".join(out), count=len(out))

    async def _callers(self, args: dict) -> ToolResult:
        await self.authorize("code.graph.get", args)
        return self._relation_report(args["name"], direction="in", verb="É chamada por")

    async def _callees(self, args: dict) -> ToolResult:
        await self.authorize("code.graph.get", args)
        return self._relation_report(args["name"], direction="out", verb="Chama")

    async def _impact(self, args: dict) -> ToolResult:
        await self.authorize("code.graph.analyze", args)
        store = self._graph()
        nodes = self._find(store, args["name"], ("function",))
        if not nodes:
            return ToolResult.error(f"Função '{args['name']}' não encontrada no código.")
        depth = max(1, int(args.get("depth") or 3))
        # BFS reversa em 'calls': tudo que depende (direta/indiretamente) desta função
        seen: set[str] = set()
        frontier = {n.id for n in nodes}
        for _ in range(depth):
            nxt: set[str] = set()
            for nid in frontier:
                for src, _rel in store.neighbors(nid, relation="calls", direction="in"):
                    if src not in seen:
                        seen.add(src); nxt.add(src)
            frontier = nxt
            if not frontier:
                break
        if not seen:
            return ToolResult.success(
                f"Nada chama '{args['name']}' (por nome único) — impacto local.", impacted=0)
        quals = sorted(_qual(store.get_node(i)) for i in seen if store.get_node(i))
        body = "\n".join(f"  • {q}" for q in quals)
        return ToolResult.success(
            f"Alterar '{args['name']}' pode afetar {len(quals)} função(ões) "
            f"(até {depth} níveis):\n{body}\n\nDica: rode os testes que cobrem esses pontos.",
            impacted=len(quals),
        )

    def _relation_report(self, name: str, *, direction: str, verb: str) -> ToolResult:
        store = self._graph()
        nodes = self._find(store, name, ("function",))
        if not nodes:
            return ToolResult.error(f"Função '{name}' não encontrada no código.")
        quals: set[str] = set()
        for n in nodes:
            for other, _rel in store.neighbors(n.id, relation="calls", direction=direction):
                node = store.get_node(other)
                if node:
                    quals.add(_qual(node))
        if not quals:
            return ToolResult.success(f"{verb} nada (resolvido por nome único).", count=0)
        body = "\n".join(f"  • {q}" for q in sorted(quals))
        return ToolResult.success(f"{name} — {verb.lower()}:\n{body}", count=len(quals))

    def _owner_file(self, store, node) -> str:
        """Sobe pela relação 'defines' até o módulo p/ achar o arquivo."""
        cur = node
        for _ in range(6):
            if cur.type == "module":
                return cur.attrs.get("file", _qual(cur))
            ins = store.neighbors(cur.id, relation="defines", direction="in")
            if not ins:
                break
            cur = store.get_node(ins[0][0]) or cur
        return _qual(node).rsplit(".", 1)[0]
