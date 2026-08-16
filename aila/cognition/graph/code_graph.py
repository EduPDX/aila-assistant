"""Code Graph — "como o software funciona" (Fase 5).

Constrói o grafo estrutural do PRÓPRIO código Python da Aila usando SÓ a stdlib
(`ast`) — ZERO dependência nova (nem tree-sitter). Reusa o mesmo GraphStore da
Fase 2; nós de código têm ``type`` em {module, class, function} (distintos dos
nós do Knowledge Graph — user/concept), o que permite a ponte futura
(concept —maps_to→ code_node) sem fundir os dois grafos.

Rótulos de confiança (inspirados no Graphify), gravados em ``provenance.label``:
  - EXTRACTED: fato direto da AST (defines, imports) → confiança 1.0.
  - INFERRED : chamada resolvida por nome ÚNICO no projeto → confiança 0.6.
  - (ambíguo): chamada com nome batendo em >1 função → NÃO vira aresta (contada).

Idempotente (upserts por id determinístico). tree-sitter p/ outras linguagens
fica como extensão opcional futura — não é necessário p/ a Aila entender a si mesma.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aila.cognition.graph.graph_store import GraphStore

from aila.core.logging import get_logger

log = get_logger("code_graph")

CODE_TYPES = ("module", "class", "function")
_DEF = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_EXCLUDE = {".venv", "venv", "node_modules", ".git", "__pycache__", "build", "dist", "vendor"}


def _cid(dotted: str) -> str:
    """Id de nó de código (prefixo evita colisão com entidades do KG)."""
    return f"code:{dotted}"


def _call_name(func: ast.expr) -> str | None:
    """Nome simples do alvo de uma chamada: foo() → 'foo', a.b.run() → 'run'."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class CodeGraph:
    def __init__(self, graph: GraphStore, root: str | Path) -> None:
        self.graph = graph
        self.root = Path(root).resolve()

    # ------------------------------------------------------------------ #
    def build(self, *, subdir: str | None = None) -> dict[str, Any]:
        """Varre .py sob root (ou root/subdir), popula o grafo, retorna relatório."""
        base = self.root / subdir if subdir else self.root
        report = {"files": 0, "errors": 0, "modules": 0, "classes": 0,
                  "functions": 0, "defines": 0, "imports": 0, "calls": 0, "ambiguous_calls": 0}
        imports: list[tuple[str, str]] = []          # (module_dotted, imported_dotted)
        callsites: list[tuple[str, str]] = []        # (caller_id, callee_simple_name)
        func_by_name: dict[str, list[str]] = defaultdict(list)  # simple name -> [node_id]

        for f in sorted(base.rglob("*.py")):
            if any(part in _EXCLUDE for part in f.relative_to(self.root).parts):
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
                report["errors"] += 1
                log.warning(f"pulei {f.name}: {exc!r}")
                continue
            report["files"] += 1
            mod = self._module_name(f)
            mid = _cid(mod)
            self.graph.upsert_node(mid, "module", mod,
                                   attrs={"file": str(f.relative_to(self.root)), "qualname": mod})
            report["modules"] += 1
            self._walk(tree.body, mid, mod, report, callsites, func_by_name)
            for imp in self._imports(tree):
                imports.append((mod, imp))

        report["imports"] = self._link_imports(imports)
        c, amb = self._link_calls(callsites, func_by_name)
        report["calls"], report["ambiguous_calls"] = c, amb
        log.info(f"code graph: {report}")
        return report

    # ------------------------------------------------------------------ #
    def _module_name(self, f: Path) -> str:
        parts = list(f.resolve().relative_to(self.root).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)

    def _walk(self, body: list, scope_id: str, scope_dotted: str, report: dict,
              callsites: list, func_by_name: dict) -> None:
        """Registra classes/funções aninhadas + arestas 'defines' (EXTRACTED)."""
        for stmt in body:
            if isinstance(stmt, ast.ClassDef):
                dotted = f"{scope_dotted}.{stmt.name}"
                nid = _cid(dotted)
                self.graph.upsert_node(nid, "class", stmt.name,
                                       attrs={"qualname": dotted, "lineno": stmt.lineno})
                self._defines(scope_id, nid, report)
                report["classes"] += 1
                self._walk(stmt.body, nid, dotted, report, callsites, func_by_name)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                dotted = f"{scope_dotted}.{stmt.name}"
                nid = _cid(dotted)
                self.graph.upsert_node(nid, "function", stmt.name,
                                       attrs={"qualname": dotted, "lineno": stmt.lineno})
                self._defines(scope_id, nid, report)
                report["functions"] += 1
                func_by_name[stmt.name].append(nid)
                for callee in self._direct_calls(stmt.body):
                    callsites.append((nid, callee))
                self._walk(stmt.body, nid, dotted, report, callsites, func_by_name)

    def _defines(self, src: str, tgt: str, report: dict) -> None:
        self.graph.upsert_edge(src, tgt, "defines", confidence=1.0,
                               provenance={"label": "EXTRACTED"})
        report["defines"] += 1

    @staticmethod
    def _direct_calls(body: list) -> list[str]:
        """Nomes chamados no corpo de uma função, SEM entrar em defs aninhadas
        (essas atribuem suas chamadas a si mesmas)."""
        names, stack = [], list(body)
        while stack:
            n = stack.pop()
            if isinstance(n, _DEF):
                continue                       # fronteira de escopo
            if isinstance(n, ast.Call) and (nm := _call_name(n.func)):
                names.append(nm)
            stack.extend(ast.iter_child_nodes(n))
        return names

    @staticmethod
    def _imports(tree: ast.Module) -> list[str]:
        out = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                out.extend(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                out.extend(f"{n.module}.{a.name}" for a in n.names)
                out.append(n.module)
        return out

    def _link_imports(self, imports: list[tuple[str, str]]) -> int:
        """Arestas 'imports' só p/ alvos internos (nós que existem no grafo)."""
        made = 0
        for mod, target in imports:
            src = _cid(mod)
            # resolve o alvo mais específico que EXISTE: símbolo (A.B) ou módulo (A)
            for cand in (target, target.rsplit(".", 1)[0]):
                tid = _cid(cand)
                if cand and cand != mod and self.graph.get_node(tid) is not None:
                    self.graph.upsert_edge(src, tid, "imports", confidence=1.0,
                                           provenance={"label": "EXTRACTED"})
                    made += 1
                    break
        return made

    def _link_calls(self, callsites: list[tuple[str, str]],
                    func_by_name: dict[str, list[str]]) -> tuple[int, int]:
        """Resolve chamadas por nome ÚNICO (INFERRED). Ambíguas (>1) são contadas
        mas NÃO viram aresta — conservador, evita ligações erradas."""
        made = ambiguous = 0
        seen: set[tuple[str, str]] = set()
        for caller, name in callsites:
            cands = func_by_name.get(name, [])
            if len(cands) == 1:
                tgt = cands[0]
                if tgt != caller and (caller, tgt) not in seen:
                    self.graph.upsert_edge(caller, tgt, "calls", confidence=0.6,
                                           provenance={"label": "INFERRED"})
                    seen.add((caller, tgt))
                    made += 1
            elif len(cands) > 1:
                ambiguous += 1
        return made, ambiguous
