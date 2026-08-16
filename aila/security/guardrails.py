"""Guardrails — trilhos leves de entrada/saída (Fase 7).

Camada FINA que COMPLEMENTA (não substitui) o resto da segurança:
``authorize()`` decide SE uma ação roda; o ``policy`` classifica risco; o
``injection`` protege o conteúdo que ENTRA de terceiros. Falta o trilho de
SAÍDA: impedir que a Aila, sem querer, ECOE um segredo que viu (uma chave num
arquivo, um token numa config, a saída de um comando) na resposta ao usuário —
que dispara TTS e é gravada no contexto/memória.

Reimplementação enxuta da ideia do NeMo Guardrails (só a camada, sem Colang):

    - INPUT  rail : delega ao ``injection`` (scan/wrap) — já cobrimos isso.
    - OUTPUT rail : ``check_output`` redige segredos ANTES de exibir/falar/gravar.

Regra de ouro: NUNCA logar o valor do segredo — só o TIPO e a contagem. Determinístico,
offline, sem dependências. Conservador: só redige o que casa com formatos de
segredo conhecidos (não mexe em prosa comum).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from aila.security import injection

if TYPE_CHECKING:
    from aila.core.config import SecurityConfig

_PLACEHOLDER = "«segredo removido»"

# Formatos de segredo conhecidos → (tipo, regex). Ordem importa (mais específico
# antes do genérico). Só formatos com baixa chance de falso-positivo em prosa.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL)),
    ("openai_key", re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}")),
    ("google_key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[0-9A-Za-z]{36,}")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*")),
    # atribuição explícita: api_key = "...."  /  password: '....'
    ("assigned_secret", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?token)\b"
        r"\s*[:=]\s*['\"]?([^\s'\"]{6,})")),
]


@dataclass(slots=True)
class GuardrailResult:
    text: str
    findings: list[str] = field(default_factory=list)   # tipos (nunca o valor!)

    @property
    def modified(self) -> bool:
        return bool(self.findings)


class Guardrails:
    """Trilhos de saída (e fachada de entrada). Barato o suficiente p/ rodar em
    todo turno; se ``cfg.guardrails`` for False, vira no-op transparente."""

    def __init__(self, cfg: SecurityConfig | None = None) -> None:
        self.cfg = cfg
        self.enabled = getattr(cfg, "guardrails", True) if cfg is not None else True

    # ----------------------------- saída ------------------------------- #
    def check_output(self, text: str) -> GuardrailResult:
        """Redige segredos conhecidos. Retorna texto limpo + TIPOS achados."""
        if not text or not self.enabled:
            return GuardrailResult(text or "")
        findings: list[str] = []
        out = text
        for kind, rx in _SECRET_PATTERNS:
            def _sub(m: re.Match[str]) -> str:
                # p/ 'assigned_secret' preserva o rótulo, redige só o valor (grupo 2)
                if m.re.groups >= 2 and m.group(2) is not None:
                    return m.group(0).replace(m.group(2), _PLACEHOLDER)
                return _PLACEHOLDER
            out, n = rx.subn(_sub, out)
            if n:
                findings.extend([kind] * n)
        return GuardrailResult(out, findings)

    # ---------------------------- entrada ------------------------------ #
    def wrap_untrusted(self, content: str, source: str = "ferramenta") -> str:
        """Fachada do trilho de ENTRADA (delega ao injection — sem duplicar)."""
        return injection.wrap_external(content, source=source)

    def scan_untrusted(self, content: str) -> list[str]:
        return injection.scan(content)
