"""Experiência atual (Fase E) — "o que eu estou fazendo agora".

Estado temporário, derivado do que a Aila REALMENTE está executando (as
ferramentas do turno), não de adivinhação sobre o texto. É o que permite
responder "estou pesquisando isso" em vez de "o sistema está pesquisando".

Determinístico e barato: um dicionário de prefixos, sem LLM.
"""

from __future__ import annotations

#: prefixo/nome da ferramenta → atividade canônica
_POR_FERRAMENTA: tuple[tuple[str, str], ...] = (
    ("web.search", "searching"),
    ("web.", "reading"),
    ("code.test", "testing"),
    ("code.lint", "testing"),
    ("code.review", "reviewing"),
    ("code.read_file", "reading"),
    ("code.map", "reading"),
    ("code.", "coding"),
    ("file.read", "reading"),
    ("file.grep", "searching"),
    ("file.glob", "searching"),
    ("file.", "editing"),
    ("vision.", "looking"),
    ("memory.", "remembering"),
    ("computer.", "operating"),
    ("git.", "reviewing"),
    ("project.", "analyzing"),
    ("skill.", "working"),
    ("avatar.", "gesturing"),
)

#: atividade → como ela DIZ isso (1ª pessoa, pt-BR)
_EM_PORTUGUES: dict[str, str] = {
    "idle": "",
    "thinking": "pensando",
    "talking": "conversando",
    "searching": "pesquisando",
    "reading": "lendo",
    "coding": "programando",
    "editing": "mexendo em arquivos",
    "testing": "testando o código",
    "reviewing": "revisando",
    "analyzing": "analisando",
    "looking": "olhando a tela",
    "remembering": "lembrando de algo",
    "operating": "usando o computador",
    "gesturing": "me mexendo",
    "working": "trabalhando nisso",
}


def activity_for_tool(tool_name: str) -> str | None:
    """Atividade correspondente a uma ferramenta (None se não mapeada)."""
    nome = (tool_name or "").strip()
    for prefixo, atividade in _POR_FERRAMENTA:
        if nome == prefixo or nome.startswith(prefixo):
            return atividade
    return None


def activity_for_tools(tools: list[str] | tuple[str, ...]) -> str:
    """Atividade do turno a partir das ferramentas usadas.

    A ÚLTIMA ferramenta reconhecida vence: é o que ela está fazendo agora
    (ex.: pesquisou e depois passou a ler a página → 'lendo')."""
    atual = "idle"
    for t in tools or ():
        a = activity_for_tool(t)
        if a:
            atual = a
    return atual


def describe(activity: str, attention: str = "") -> str:
    """Frase em 1ª pessoa ('' quando não há nada a dizer)."""
    pt = _EM_PORTUGUES.get(activity or "idle", "")
    if not pt:
        return ""
    return f"estou {pt}" + (f" ({attention})" if attention else "")
