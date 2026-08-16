"""AgentManager — instancia os agentes habilitados e monta o registro de tools."""

from __future__ import annotations

from aila.agents.avatar_agent import AvatarAgent
from aila.agents.base import AgentDeps, BaseAgent
from aila.agents.binary_agent import BinaryAgent
from aila.agents.code_agent import CodeAgent
from aila.agents.computer_agent import ComputerAgent
from aila.agents.document_agent import DocumentAgent
from aila.agents.file_agent import FileAgent
from aila.agents.git_agent import GitAgent
from aila.agents.memory_agent import MemoryAgent
from aila.agents.vision_agent import VisionAgent
from aila.agents.web_agent import WebAgent
from aila.core.logging import get_logger
from aila.tools.registry import ToolRegistry

log = get_logger("agent_manager")

# Registro de agentes conhecidos (nome -> classe).
AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "file": FileAgent,
    "code": CodeAgent,
    "documents": DocumentAgent,
    "git": GitAgent,
    "web": WebAgent,
    "computer": ComputerAgent,
    "vision": VisionAgent,
    "binary": BinaryAgent,
    "memory": MemoryAgent,
    "avatar": AvatarAgent,
}


class AgentManager:
    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps
        self.agents: dict[str, BaseAgent] = {}
        self.registry = ToolRegistry(timeout=deps.settings.security.tool_timeout)
        self._build()

    def _build(self) -> None:
        enabled = self.deps.settings.agents.enabled
        for name in enabled:
            cls = AGENT_CLASSES.get(name)
            if cls is None:
                log.warning(f"agente desconhecido em config: {name}")
                continue
            agent = cls(self.deps)
            self.agents[name] = agent
            for tool in agent.tools():
                self.registry.register(tool)
            log.info(f"agente habilitado: {name}")

    def describe_capabilities(self) -> str:
        """Texto para o prompt de sistema, descrevendo o que a IA pode fazer."""
        lines = ["Você tem acesso aos seguintes agentes e ferramentas:"]
        for name, agent in self.agents.items():
            lines.append(f"\n• {name}: {agent.description}")
            for tool in agent.tools():
                lines.append(f"    - {tool.name}: {tool.description}")
        # tools que NÃO pertencem a um agente (skills, servidores MCP externos) —
        # registradas direto no registry. Agrupa por 'dono' p/ ficar legível.
        extra: dict[str, list] = {}
        for tool in self.registry.all():
            if tool.agent not in self.agents:
                extra.setdefault(tool.agent, []).append(tool)
        _labels = {"skill": "receitas nomeadas (compõem outras ferramentas)",
                   "mcp": "ferramentas de servidores MCP externos"}
        for owner, tools in extra.items():
            lines.append(f"\n• {owner}: {_labels.get(owner, owner)}")
            for tool in tools:
                lines.append(f"    - {tool.name}: {tool.description}")
        return "\n".join(lines)
