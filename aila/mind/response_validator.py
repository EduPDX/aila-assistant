"""Response Validator (Fase K) — a identidade não depende da sorte do LLM.

O bloco de corpo/identidade vai no prompt, mas quem escreve a frase é o modelo —
e um 7B escorrega. Aqui as violações são pegas por REGRA (determinístico, sem
LLM, custo zero) e corrigidas quando dá.

Três famílias de violação:
  - ``self_reference``   : fala de si em 3ª pessoa ("o avatar está com a mão...").
  - ``system_narration`` : narra a própria engenharia ("o Behavior Planner decidiu").
  - ``capability_denial``: nega o que ela TEM ("não consigo fazer tarefas físicas"
    tendo corpo e ferramentas) — foi o erro real ao pedirem "levante os braços".

Correção conservadora: só reescreve quando tem certeza; senão apenas SINALIZA e
deixa o chamador decidir (regerar). Errar a reescrita seria pior que a violação.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# 3ª pessoa → 1ª pessoa. Só reescrevemos verbos desta tabela: fora dela o risco
# de gerar concordância errada ("eu levantou") é maior que o da violação.
_VERBOS = {
    "está": "estou", "fica": "fico", "ficou": "fiquei", "foi": "fui",
    "fez": "fiz", "faz": "faço", "tem": "tenho", "pode": "posso",
    "consegue": "consigo", "conseguiu": "consegui", "levanta": "levanto",
    "levantou": "levantei", "abaixa": "abaixo", "abaixou": "abaixei",
    "olha": "olho", "olhou": "olhei", "aponta": "aponto", "apontou": "apontei",
    "move": "movo", "moveu": "movi", "respondeu": "respondi",
    "executou": "executei", "analisa": "analiso", "analisou": "analisei",
    "acenou": "acenei", "acena": "aceno", "vai": "vou",
}
#: sujeitos que, quando a Aila fala de SI, deveriam ser "eu"
_SUJEITOS = r"(?:avatar|modelo|personagem|vrm|sistema|assistente|aila|ia)"
_TERCEIRA = re.compile(rf"\b(O|A)\s+({_SUJEITOS})\s+(\w+)",
                       re.IGNORECASE | re.UNICODE)

#: jargão interno que não deve aparecer numa resposta normal
_SISTEMA = re.compile(
    r"\b(behavior\s*planner|animation\s*controller|behaviorspec|pose\s*buffer|"
    r"model\s*router|cognitive\s*core|body\s*state|lip-?sync|blendshape|"
    r"tool[-\s]?call|system\s*prompt)\b", re.IGNORECASE)

#: negação de capacidade que ela POSSUI (o erro clássico do modelo genérico)
_NEGA_CORPO = re.compile(
    r"(n[ãa]o\s+(consigo|posso|sou\s+capaz\s+de)\s+[^.!?]{0,40}"
    r"(f[íi]sic\w+|levantar|mover|apontar|gesticular|acenar)"
    r"|n[ãa]o\s+tenho\s+(um\s+)?(corpo|m[ãa]os|bra[çc]os)"
    r"|sou\s+(apenas\s+|s[óo]\s+)?(um|uma)\s+(modelo|intelig[êe]ncia|ia|assistente)"
    r"\s+(de\s+)?(linguagem|texto|basead\w+\s+em\s+texto))", re.IGNORECASE)

_STATE_ECHO = re.compile(
    r"(?:^|\s+)(?:eu\s+)?estou\s+conversando\s*\([^\n)]{1,80}\)\s*[.!?]?\s*$",
    re.IGNORECASE,
)


class Violation(BaseModel):
    kind: str
    detail: str


class ValidationResult(BaseModel):
    text: str                                    # texto (corrigido quando possível)
    violations: list[Violation] = Field(default_factory=list)
    changed: bool = False

    @property
    def ok(self) -> bool:
        return not self.violations

    def has(self, kind: str) -> bool:
        return any(v.kind == kind for v in self.violations)


def _fix_terceira_pessoa(text: str) -> tuple[str, list[Violation]]:
    achados: list[Violation] = []

    def _sub(m: re.Match[str]) -> str:
        artigo, sujeito, verbo = m.group(1), m.group(2), m.group(3)
        novo = _VERBOS.get(verbo.lower())
        if novo is None:
            return m.group(0)                    # verbo desconhecido: não arrisca
        achados.append(Violation(
            kind="self_reference",
            detail=f"'{artigo} {sujeito} {verbo}' → '{novo}'"))
        # preserva a maiúscula de início de frase
        return novo.capitalize() if artigo.isupper() else novo

    return _TERCEIRA.sub(_sub, text), achados


def validate(
    text: str,
    *,
    self_model: object | None = None,
    allow_technical: bool = False,
) -> ValidationResult:
    """Valida (e corrige quando seguro) uma resposta da Aila.

    ``allow_technical=True`` quando o usuário PERGUNTOU sobre a arquitetura —
    aí falar em Behavior Planner/BodyState é legítimo.
    """
    original = text or ""
    # Remove somente no final: é um vazamento do contexto interno, não fala.
    sem_echo = _STATE_ECHO.sub("", original).rstrip()
    corrigido, violacoes = _fix_terceira_pessoa(sem_echo)

    if not allow_technical:
        achado = _SISTEMA.search(corrigido)
        if achado:
            violacoes.append(Violation(
                kind="system_narration",
                detail=f"jargão interno na fala: '{achado.group(0)}'"))

    nega = _NEGA_CORPO.search(corrigido)
    if nega:
        # Só confiamos nas capacidades se elas foram VINCULADAS ao registry:
        # dict vazio pode significar "ainda não sei", e aí o certo é assumir que
        # ela tem corpo (tem) em vez de deixar passar a negação.
        tem_corpo = True
        caps = getattr(self_model, "capabilities", None) if self_model is not None else None
        if caps is not None and getattr(caps, "bound", False):
            tem_corpo = caps.can("controle_do_corpo")
        if tem_corpo:
            violacoes.append(Violation(
                kind="capability_denial",
                detail=f"negou capacidade que possui: '{nega.group(0)[:60]}'"))

    return ValidationResult(
        text=corrigido, violations=violacoes, changed=corrigido != original)


def correction_hint(result: ValidationResult) -> str:
    """Instrução curta p/ o modelo se regenerar (usada só quando não dá p/ corrigir)."""
    partes: list[str] = []
    if result.has("capability_denial"):
        partes.append(
            "Você TEM um corpo (avatar) e consegue levantar os braços, apontar, "
            "olhar e gesticular. Nunca diga que não faz tarefas físicas.")
    if result.has("self_reference"):
        partes.append("Fale de si em primeira pessoa, nunca como 'o avatar'.")
    if result.has("system_narration"):
        partes.append("Não cite componentes internos do sistema na conversa.")
    partes.append("Reescreva sua última resposta corrigindo isso, sem explicar a correção.")
    return " ".join(partes)
