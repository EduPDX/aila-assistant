"""Classe base para todos os agentes.

Um agente é um módulo que:
    - declara um conjunto de ferramentas (``tools()``),
    - passa toda ação sensível pelo ``PermissionManager`` antes de executar.

Dependências comuns (permissões, sandbox, LLM) são injetadas via ``AgentDeps``,
evitando acoplamento a singletons e facilitando testes.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass

from aila.core.config import Settings
from aila.llm.base import LLMBackend
from aila.security.permissions import PermissionManager
from aila.security.sandbox import PathSandbox
from aila.tools.schema import Tool


@dataclass(slots=True)
class AgentDeps:
    settings: Settings
    permissions: PermissionManager
    sandbox: PathSandbox
    llm: LLMBackend


class BaseAgent(abc.ABC):
    #: identificador curto do agente (ex.: "file")
    name: str = "base"
    #: descrição usada no prompt de sistema para o roteamento
    description: str = ""

    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps

    @abc.abstractmethod
    def tools(self) -> list[Tool]:
        """Retorna as ferramentas expostas por este agente."""
        raise NotImplementedError

    async def authorize(self, action: str, params: dict) -> None:
        """Passa a ação pelo gerenciador de permissões."""
        await self.deps.permissions.check(action, self.name, params)
