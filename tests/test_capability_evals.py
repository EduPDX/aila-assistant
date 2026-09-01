from __future__ import annotations

import asyncio

from aila.core.capability_evals import CapabilityEvalCase, evaluate_case
from aila.core.turn import (
    _classify_task,
    requires_concrete_tool_action,
    select_tool_schemas,
)
from aila.llm.base import ChatChunk, LLMBackend
from aila.tools.registry import ToolRegistry
from aila.tools.schema import Tool, ToolResult


async def _unused(args: dict) -> ToolResult:
    return ToolResult.success("não executada")


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name in ("file.write", "code.write_file", "file.list", "web.search"):
        registry.register(Tool(name=name, description=name, params=[], handler=_unused, agent="eval"))
    return registry


class _NativeToolBackend(LLMBackend):
    async def chat(self, messages, **kwargs):
        yield ChatChunk(
            content="",
            done=True,
            tool_calls=[{"function": {"name": "file.write", "arguments": {}}}],
        )

    async def complete(self, messages, **kwargs):
        return ""

    async def list_models(self):
        return ["fake"]

    async def health(self):
        return True


class _TextToolBackend(_NativeToolBackend):
    async def chat(self, messages, **kwargs):
        yield ChatChunk(
            content='```json\n{"name":"code.write_file","arguments":{}}\n```',
            done=True,
        )


def test_eval_accepts_expected_native_tool_without_executing_it():
    registry = _registry()
    result = asyncio.run(evaluate_case(
        _NativeToolBackend(),
        "fake",
        "system",
        registry.schemas(),
        registry,
        CapabilityEvalCase("write", "salve", expected_tools=("file.write",)),
    ))
    assert result.passed is True
    assert result.selected_tools == ["file.write"]


def test_eval_rejects_forbidden_textual_tool_call():
    registry = _registry()
    result = asyncio.run(evaluate_case(
        _TextToolBackend(),
        "fake",
        "system",
        registry.schemas(),
        registry,
        CapabilityEvalCase(
            "wrong_write",
            "salve nos Documentos",
            expected_tools=("file.write",),
            forbidden_tools=("code.write_file",),
        ),
    ))
    assert result.passed is False
    assert result.selected_tools == ["code.write_file"]
    assert "proibida" in result.reason


def test_eval_rejects_tools_in_casual_chat():
    registry = _registry()
    result = asyncio.run(evaluate_case(
        _NativeToolBackend(),
        "fake",
        "system",
        registry.schemas(),
        registry,
        CapabilityEvalCase("casual", "oi", expect_no_tool=True),
    ))
    assert result.passed is False
    assert "conversa casual" in result.reason


def test_tool_selector_removes_self_edit_for_personal_file():
    registry = _registry()
    prompt = "Crie um jogo em Java e salve em Documentos como Cobra.java"
    task, use_tools = _classify_task(prompt, "auto")
    schemas = select_tool_schemas(registry, task, prompt)
    names = [schema["function"]["name"] for schema in schemas]
    assert use_tools is True
    assert names == ["file.write"]


def test_personal_code_write_requires_concrete_tool_action():
    prompt = "Crie um jogo em Java e salve em Documentos como Jogo.java"
    task, use_tools = _classify_task(prompt, "auto")
    schemas = [{"type": "function", "function": {"name": "file.write"}}]

    assert use_tools is True
    assert requires_concrete_tool_action(task, prompt, schemas) is True


def test_casual_turn_never_requires_concrete_tool_action():
    task, use_tools = _classify_task("Olá Aila, como vai?", "auto")

    assert use_tools is False
    assert requires_concrete_tool_action(task, "Olá Aila, como vai?", None) is False


def test_tool_selector_limits_personal_folder_listing():
    registry = _registry()
    prompt = "Liste o que tem na pasta Documentos"
    task, use_tools = _classify_task(prompt, "auto")
    schemas = select_tool_schemas(registry, task, prompt)
    assert use_tools is True
    assert [schema["function"]["name"] for schema in schemas] == ["file.list"]


def test_research_has_distinct_route_kind():
    task, use_tools = _classify_task(
        "Pesquise na web as notícias mais recentes sobre IA", "auto"
    )
    assert task.kind == "research"
    assert use_tools is True
