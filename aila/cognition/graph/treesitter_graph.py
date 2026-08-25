"""Code Graph multi-linguagem via tree-sitter (extensão da Fase 5).

Produz o MESMO modelo de nós/arestas do :mod:`code_graph` (que usa ``ast`` p/
Python), mas para outras linguagens — JavaScript/TypeScript, Go e Rust — usando
o tree-sitter (wheels pré-compilados; abi3, funciona no 3.14). É ADITIVO: o
builder Python continua intacto e preciso; este cobre o resto.

Nós: ``module`` / ``class`` / ``function`` (mesmos tipos), id ``code:<qualname>``.
Arestas:
  - ``defines`` (EXTRACTED, 1.0): escopo → definição aninhada.
  - ``calls``   (INFERRED, 0.6): chamada resolvida por nome ÚNICO no arquivo-conjunto
    (ambíguas — nome batendo em >1 função — são contadas, não viram aresta).

Sem tree-sitter instalado, :func:`available` devolve False e o chamador degrada
(o grafo Python continua funcionando). NUNCA levanta por arquivo com erro de
parse — pula e conta.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aila.cognition.graph.code_graph import _EXCLUDE, _cid
from aila.core.logging import get_logger

if TYPE_CHECKING:
    from aila.cognition.graph.graph_store import GraphStore

log = get_logger("treesitter_graph")

# extensão → linguagem do tree-sitter-language-pack
_LANG_EXT: dict[str, str] = {
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".rs": "rust",
}

# tipos de nó que DEFINEM algo nomeado (via campo 'name') → nosso tipo
_DEF_TYPES: dict[str, str] = {
    "function_declaration": "function", "generator_function_declaration": "function",
    "function_definition": "function", "function_item": "function",
    "method_definition": "function", "method_declaration": "function",
    "class_declaration": "class", "class_definition": "class",
    "struct_item": "class", "enum_item": "class", "trait_item": "class",
    "interface_declaration": "class", "type_spec": "class",   # Go: type X struct{}
}
_CALL_TYPES = {"call_expression", "call"}
_ARROW_VALUE = {"arrow_function", "function", "function_expression"}

_parsers: dict[str, Any] = {}   # cache de parsers por linguagem


def available() -> bool:
    """True se o tree-sitter e o language-pack estão instalados."""
    import importlib.util

    return (importlib.util.find_spec("tree_sitter") is not None
            and importlib.util.find_spec("tree_sitter_language_pack") is not None)


def _parser(lang: str):
    if lang not in _parsers:
        from tree_sitter_language_pack import get_parser

        _parsers[lang] = get_parser(lang)
    return _parsers[lang]


def _text(node) -> str:      # noqa: ANN001
    return node.text.decode("utf-8", "replace")


def _def_our_type(node) -> str | None:      # noqa: ANN001
    """Nosso tipo p/ um nó de definição, ou None. Trata `const f = () => …`."""
    t = node.type
    if t in _DEF_TYPES:
        return _DEF_TYPES[t]
    if t == "variable_declarator":           # JS/TS: função atribuída a uma const/var
        val = node.child_by_field_name("value")
        if val is not None and val.type in _ARROW_VALUE:
            return "function"
    return None


def _def_name(node) -> str | None:      # noqa: ANN001
    nm = node.child_by_field_name("name")
    return _text(nm) if nm is not None else None


def _last_ident(node) -> str | None:      # noqa: ANN001
    """Nome simples do alvo de uma chamada: foo() → 'foo'; a.b.run() → 'run';
    pkg::mod::f() → 'f'. Percorre member/selector/field/scoped até o identificador."""
    if node is None:
        return None
    if node.type.endswith("identifier"):
        return _text(node)
    for field in ("property", "field", "name"):
        c = node.child_by_field_name(field)
        if c is not None:
            return _last_ident(c)
    idents = [c for c in node.children if c.type.endswith("identifier")]
    return _text(idents[-1]) if idents else None


def _callee_name(call) -> str | None:      # noqa: ANN001
    fn = call.child_by_field_name("function") or call.child_by_field_name("callee")
    if fn is None and call.children:
        fn = call.children[0]
    return _last_ident(fn)


class TreeSitterGraph:
    def __init__(self, graph: GraphStore, root: str | Path) -> None:
        self.graph = graph
        self.root = Path(root).resolve()

    def build(self) -> dict[str, Any]:
        """Varre fontes não-Python sob root, popula o grafo, devolve relatório."""
        report: dict[str, Any] = {"files": 0, "errors": 0, "modules": 0, "classes": 0,
                                  "functions": 0, "defines": 0, "calls": 0,
                                  "ambiguous_calls": 0, "by_lang": {}}
        callsites: list[tuple[str, str]] = []
        func_by_name: dict[str, list[str]] = defaultdict(list)

        files = [
            f for f in sorted(self.root.rglob("*"))
            if f.suffix.lower() in _LANG_EXT and f.is_file()
            and not any(part in _EXCLUDE for part in f.relative_to(self.root).parts)
        ]
        for f in files:
            lang = _LANG_EXT[f.suffix.lower()]
            try:
                src = f.read_bytes()
                tree = _parser(lang).parse(src)
            except Exception as exc:  # noqa: BLE001 - parse/IO nunca aborta o build todo
                report["errors"] += 1
                log.warning(f"pulei {f.name}: {exc!r}")
                continue
            report["files"] += 1
            report["by_lang"][lang] = report["by_lang"].get(lang, 0) + 1
            mod = self._module_name(f)
            mid = _cid(mod)
            self.graph.upsert_node(mid, "module", mod, attrs={
                "file": str(f.relative_to(self.root)), "qualname": mod, "lang": lang})
            report["modules"] += 1
            self._walk(tree.root_node, mid, mod, None, report, callsites, func_by_name)

        c, amb = self._link_calls(callsites, func_by_name)
        report["calls"], report["ambiguous_calls"] = c, amb
        log.info(f"tree-sitter graph: {report}")
        return report

    def _module_name(self, f: Path) -> str:
        parts = list(f.resolve().relative_to(self.root).with_suffix("").parts)
        return ".".join(parts)

    def _walk(self, node, scope_id: str, scope_dotted: str, enclosing_func: str | None,  # noqa: ANN001
              report: dict, callsites: list, func_by_name: dict) -> None:
        """Percorre a árvore: cria nós de def + arestas 'defines'; atribui chamadas
        à função que as contém (fronteira de escopo, como o builder Python)."""
        for child in node.children:
            our = _def_our_type(child)
            name = _def_name(child) if our else None
            if our and name:
                dotted = f"{scope_dotted}.{name}"
                nid = _cid(dotted)
                lineno = child.start_point[0] + 1
                self.graph.upsert_node(nid, our, name,
                                       attrs={"qualname": dotted, "lineno": lineno})
                self.graph.upsert_edge(scope_id, nid, "defines", confidence=1.0,
                                       provenance={"label": "EXTRACTED"})
                report["defines"] += 1
                report["classes" if our == "class" else "functions"] += 1
                enc = nid if our == "function" else enclosing_func
                if our == "function":
                    func_by_name[name].append(nid)
                self._walk(child, nid, dotted, enc, report, callsites, func_by_name)
            else:
                if enclosing_func and child.type in _CALL_TYPES:
                    nm = _callee_name(child)
                    if nm:
                        callsites.append((enclosing_func, nm))
                self._walk(child, scope_id, scope_dotted, enclosing_func,
                           report, callsites, func_by_name)

    def _link_calls(self, callsites: list[tuple[str, str]],
                    func_by_name: dict[str, list[str]]) -> tuple[int, int]:
        """Chamadas por nome ÚNICO viram aresta (INFERRED); ambíguas são só contadas."""
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
