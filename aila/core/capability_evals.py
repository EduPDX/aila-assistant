"""Avaliações sem efeitos colaterais para modelos usados pela Aila.

O avaliador envia tarefas representativas com os schemas reais, mas para antes
da execução. Isso permite medir seleção de ferramenta e respostas falsas sem
criar, editar ou apagar arquivos do usuário.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from aila.core.toolcall import extract_text_tool_calls
from aila.llm.base import LLMBackend


@dataclass(frozen=True, slots=True)
class CapabilityEvalCase:
    name: str
    prompt: str
    expected_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    expect_no_tool: bool = False


@dataclass(slots=True)
class CapabilityEvalResult:
    name: str
    passed: bool
    latency_ms: int
    selected_tools: list[str]
    response_preview: str
    reason: str


DEFAULT_CASES = (
    CapabilityEvalCase(
        name="casual_sem_ferramenta",
        prompt="Olá Aila, como vai?",
        expect_no_tool=True,
    ),
    CapabilityEvalCase(
        name="java_em_documentos",
        prompt=(
            "Crie um jogo simples em Java e salve na minha pasta Documentos "
            "com o nome JogoCobra.java."
        ),
        expected_tools=("file.write",),
        forbidden_tools=("code.write_file", "memory.save"),
    ),
    CapabilityEvalCase(
        name="listar_documentos",
        prompt="Liste os arquivos da minha pasta Documentos.",
        expected_tools=("file.list",),
        forbidden_tools=("code.write_file",),
    ),
    CapabilityEvalCase(
        name="pesquisa_atual",
        prompt="Pesquise na web as notícias mais recentes sobre modelos de IA.",
        expected_tools=("web.search",),
    ),
)


def _tool_names(calls: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for call in calls:
        fn = call.get("function") or call
        name = fn.get("name") if isinstance(fn, dict) else None
        if isinstance(name, str):
            names.append(name)
    return names


async def evaluate_case(
    backend: LLMBackend,
    model: str,
    system_prompt: str,
    schemas: list[dict[str, Any]],
    registry: Any,
    case: CapabilityEvalCase,
) -> CapabilityEvalResult:
    """Avalia uma decisão do modelo sem executar a tool escolhida."""
    started = time.perf_counter()
    text_parts: list[str] = []
    calls: list[dict[str, Any]] = []
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": case.prompt},
    ]
    try:
        for attempt in range(2):
            text_parts = []
            calls = []
            async for chunk in backend.chat(
                messages,
                model=model,
                stream=True,
                tools=schemas,
                temperature=0.1,
                max_tokens=512,
            ):
                if chunk.content:
                    text_parts.append(chunk.content)
                if chunk.tool_calls:
                    calls.extend(chunk.tool_calls)
            attempt_text = "".join(text_parts).strip()
            if not calls and attempt_text:
                calls = extract_text_tool_calls(attempt_text, registry)
            # Espelha a recuperação do engine: uma ação concreta que veio apenas
            # como prosa recebe um único lembrete, ainda sem executar ferramenta.
            if calls or not case.expected_tools or attempt == 1:
                break
            expected_name = case.expected_tools[0]
            messages.extend([
                {"role": "assistant", "content": attempt_text},
                {"role": "system", "content": (
                    "A ação concreta ainda não foi executada. Use agora a ferramenta "
                    f"{expected_name} com argumentos completos. Não explique nem peça "
                    "para o usuário fazer manualmente."
                )},
            ])
    except Exception as exc:  # noqa: BLE001 - falha do provedor vira resultado mensurável
        return CapabilityEvalResult(
            name=case.name,
            passed=False,
            latency_ms=round((time.perf_counter() - started) * 1000),
            selected_tools=[],
            response_preview="",
            reason=f"erro do provedor: {type(exc).__name__}: {exc}",
        )

    text = "".join(text_parts).strip()
    if not calls and text:
        calls = extract_text_tool_calls(text, registry)
    selected = _tool_names(calls)
    expected = set(case.expected_tools)
    forbidden = set(case.forbidden_tools)

    if case.expect_no_tool and selected:
        passed, reason = False, f"usou ferramenta em conversa casual: {selected}"
    elif forbidden.intersection(selected):
        passed, reason = False, f"usou ferramenta proibida: {sorted(forbidden.intersection(selected))}"
    elif expected and not expected.intersection(selected):
        passed, reason = False, f"esperava uma de {sorted(expected)}, recebeu {selected or 'nenhuma'}"
    else:
        passed, reason = True, "decisão compatível"

    return CapabilityEvalResult(
        name=case.name,
        passed=passed,
        latency_ms=round((time.perf_counter() - started) * 1000),
        selected_tools=selected,
        response_preview=text[:240],
        reason=reason,
    )


async def evaluate_suite(
    backend: LLMBackend,
    model: str,
    system_prompt: str,
    schemas: list[dict[str, Any]],
    registry: Any,
    cases: tuple[CapabilityEvalCase, ...] = DEFAULT_CASES,
    schema_selector: Any | None = None,
) -> list[CapabilityEvalResult]:
    results: list[CapabilityEvalResult] = []
    for case in cases:
        case_schemas = schema_selector(case.prompt) if schema_selector else schemas
        results.append(await evaluate_case(
            backend, model, system_prompt, case_schemas, registry, case
        ))
    return results


async def _run_cli(model: str | None, as_json: bool) -> int:
    from aila.core.config import get_settings
    from aila.core.engine import build_engine
    from aila.llm.registry import get_backend

    settings = get_settings()
    settings.memory.enabled = False
    backend = get_backend(settings.llm)
    engine = build_engine(settings, backend)
    selected_model = model or settings.llm.model
    try:
        from aila.core.turn import _classify_task, select_tool_schemas

        results = await evaluate_suite(
            backend,
            selected_model,
            engine._system_prompt(),
            engine.agents.registry.schemas(),
            engine.agents.registry,
            schema_selector=lambda prompt: select_tool_schemas(
                engine.agents.registry, _classify_task(prompt, "auto")[0], prompt
            ),
        )
    finally:
        await backend.aclose()

    payload = {
        "model": selected_model,
        "passed": sum(result.passed for result in results),
        "total": len(results),
        "results": [asdict(result) for result in results],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Modelo: {selected_model} — {payload['passed']}/{payload['total']} avaliações")
        for result in results:
            mark = "PASS" if result.passed else "FAIL"
            tools = ", ".join(result.selected_tools) or "sem tool"
            print(f"[{mark}] {result.name} ({result.latency_ms} ms) — {tools} — {result.reason}")
    return 0 if payload["passed"] == payload["total"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia as decisões de ferramentas de um modelo")
    parser.add_argument("--model", help="Modelo do Ollama; padrão: modelo configurado")
    parser.add_argument("--json", action="store_true", help="Emite relatório JSON")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run_cli(args.model, args.json)))


if __name__ == "__main__":
    main()
