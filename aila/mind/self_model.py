"""AilaSelf — a representação que a Aila tem de si mesma (Fase B).

Agrega o que é ESTÁVEL (identidade, personalidade) com o que é do MOMENTO
(corpo, experiência, emoção) e com o que ela realmente CONSEGUE fazer
(capacidades, derivadas das ferramentas registradas).

Nesta fase o objeto existe e é testável, mas ainda NÃO participa do turno —
a integração vem nas fases seguintes, atrás de uma flag. Assim nada do fluxo
atual muda enquanto a fundação é construída.
"""

from __future__ import annotations

import time
from typing import Any

from aila.mind.identity import load_identity
from aila.mind.schemas import (
    AilaState,
    BodyState,
    Capabilities,
    Experience,
    Identity,
    PersonalityTraits,
)

#: prefixo→capacidade: traduz ferramentas reais em "o que eu consigo fazer".
_CAP_BY_PREFIX = {
    "web.": "pesquisa_web",
    "vision.": "visao",
    "code.": "programacao",
    "file.": "arquivos",
    "computer.": "controle_do_pc",
    "avatar.": "controle_do_corpo",
    "memory.": "memoria",
    "git.": "git",
    "project.": "projetos",
}


class AilaSelf:
    """Estado de identidade + estado atual. Fonte da verdade sobre "quem sou eu"."""

    def __init__(
        self,
        identity: Identity | None = None,
        personality: PersonalityTraits | None = None,
    ) -> None:
        self.identity = identity or Identity()
        self.personality = personality or PersonalityTraits()
        self.body = BodyState()
        self.experience = Experience()
        self.capabilities = Capabilities()

    # ------------------------------------------------------------ carga #
    @classmethod
    def load(cls, config_dir: str | None = None) -> AilaSelf:
        ident, pers = load_identity(config_dir)
        return cls(ident, pers)

    def bind_capabilities(self, registry: Any) -> None:
        """Deriva as capacidades das ferramentas REALMENTE registradas — assim a
        Aila não promete o que não tem nem nega o que tem."""
        items: dict[str, bool] = {}
        try:
            nomes = [t.name for t in registry.all()]
        except Exception:  # noqa: BLE001 - registry ausente/atípico
            nomes = []
        for n in nomes:
            for prefixo, cap in _CAP_BY_PREFIX.items():
                if n.startswith(prefixo):
                    items[cap] = True
        self.capabilities = Capabilities(items=items)

    # ----------------------------------------------------- estado atual #
    def update_body(self, **campos: Any) -> BodyState:
        """Atualiza o corpo (usado pelo body.report na Fase D)."""
        dados = self.body.model_dump()
        dados.update({k: v for k, v in campos.items() if v is not None})
        dados["updated_at"] = time.time()
        self.body = BodyState(**dados)
        return self.body

    def update_experience(self, **campos: Any) -> Experience:
        dados = self.experience.model_dump()
        dados.update({k: v for k, v in campos.items() if v is not None})
        self.experience = Experience(**dados)
        return self.experience

    # -------------------------------------------------------- contratos #
    def state(self) -> AilaState:
        """Snapshot para o frontend (sem vazar qual LLM foi usado)."""
        return AilaState(
            identity=self.identity,
            personality=self.personality.summary(),
            emotion=self.experience.emotion,
            experience=self.experience,
            body=self.body,
            capabilities=sorted(k for k, v in self.capabilities.items.items() if v),
        )

    def prompt_block(self, *, include_body: bool = True) -> str:
        """Bloco CURTO de auto-representação para o modelo.

        De propósito enxuto: com num_ctx de 8k, mandar o estado inteiro sufoca a
        janela. Vai só o essencial para a resposta sair em 1ª pessoa e coerente.
        """
        linhas = [self.identity.prompt_block(), f"Seu jeito: {self.personality.summary()}."]
        if include_body:
            corpo = self.body.describe()
            if corpo:
                linhas.append(f"Seu corpo agora: {corpo}.")
        if self.experience.activity and self.experience.activity != "idle":
            linhas.append(f"Você está: {self.experience.activity}.")
        linhas.append(
            "O avatar é o SEU corpo: fale dele como 'meu braço', 'minha mão', "
            "'estou olhando' — nunca como 'o avatar' ou 'o modelo' (esses termos "
            "só quando o assunto for a sua arquitetura técnica)."
        )
        return "\n".join(linhas)
