"""Registro central de ferramentas disponíveis para a IA."""

from __future__ import annotations

import asyncio

from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolResult

log = get_logger("tools")


class ToolRegistry:
    def __init__(self, timeout: float | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        # backstop global: nenhuma tool pode travar o agente para sempre.
        self.timeout = timeout if (timeout and timeout > 0) else None

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Ferramenta duplicada: {tool.name}")
        self._tools[tool.name] = tool
        log.debug(f"tool registrada: {tool.name} (agente {tool.agent})")

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        """Lista de JSON Schemas para enviar ao LLM."""
        return [t.json_schema() for t in self._tools.values()]

    async def execute(self, name: str, args: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.error(f"Ferramenta desconhecida: {name}")
        try:
            if self.timeout is not None:
                return await asyncio.wait_for(tool.handler(args), timeout=self.timeout)
            return await tool.handler(args)
        except TimeoutError:
            log.warning(f"tool '{name}' excedeu o tempo limite ({self.timeout}s)")
            return ToolResult.error(
                f"'{name}' excedeu o tempo limite ({self.timeout:.0f}s) e foi abortada."
            )
        except Exception as exc:  # noqa: BLE001 - queremos reportar qualquer erro à IA
            log.exception(f"erro ao executar {name}")
            return ToolResult.error(f"Erro em {name}: {exc}")
