"""Esquema de ferramentas (tools) que a IA pode invocar.

Uma Tool é uma capacidade concreta exposta por um agente (ex.: ``file.write``).
O formato de parâmetros é compatível com JSON Schema, permitindo tanto o
tool-calling nativo do Ollama quanto o protocolo JSON próprio da Aila.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

# Handler assíncrono: recebe os argumentos e retorna um ToolResult.
ToolHandler = Callable[[dict[str, Any]], Awaitable["ToolResult"]]


@dataclass(slots=True)
class ToolParam:
    name: str
    type: str  # "string" | "integer" | "boolean" | "number" | "array" | "object"
    description: str
    required: bool = True
    enum: list[str] | None = None


@dataclass(slots=True)
class ToolResult:
    ok: bool
    content: str
    data: dict[str, Any] | None = None

    @classmethod
    def success(cls, content: str, **data: Any) -> "ToolResult":
        return cls(ok=True, content=content, data=data or None)

    @classmethod
    def error(cls, content: str) -> "ToolResult":
        return cls(ok=False, content=content)


@dataclass(slots=True)
class Tool:
    name: str            # ex.: "file.write"  (namespace.acao)
    description: str
    params: list[ToolParam]
    handler: ToolHandler
    agent: str           # agente dono da tool

    def json_schema(self) -> dict[str, Any]:
        """Exporta no formato de function-calling (OpenAI/Ollama)."""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self.params:
            schema: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                schema["enum"] = p.enum
            properties[p.name] = schema
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
