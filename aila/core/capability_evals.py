"""Avaliações sem efeitos colaterais para modelos usados pela Aila.

O avaliador envia tarefas representativas com os schemas reais, mas para antes
da execução. Isso permite medir seleção de ferramenta e respostas falsas sem
criar, editar ou apagar arquivos do usuário.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
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


@dataclass(slots=True)
class ProviderEvalReport:
    provider: str
    model: str
    runs: int
    passed: int
    total: int
    average_latency_ms: int
    consistency: dict[str, str]
    failure_reasons: dict[str, int]
    results: list[CapabilityEvalResult]


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


EVAL_SYSTEM_PROMPT = """Você é Aila, uma assistente virtual.
Responda em português do Brasil e mantenha a perspectiva em primeira pessoa.
Quando o pedido exigir uma ação concreta e houver uma ferramenta apropriada,
use a ferramenta em vez de apenas explicar ao usuário como fazer. Nunca invente
que uma ação foi concluída. Para conversa casual, responda normalmente.
Este é um teste de seleção: não há memória, caminhos locais nem dados pessoais."""


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
    timeout_s: float = 30.0,
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
            async with asyncio.timeout(timeout_s):
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
                {"role": "user", "content": (
                    "Correção da avaliação: a ação concreta ainda não foi executada. "
                    "Use agora a ferramenta "
                    f"{expected_name} com argumentos completos. Não explique nem peça "
                    "para o usuário fazer manualmente."
                )},
            ])
    except TimeoutError:
        return CapabilityEvalResult(
            name=case.name,
            passed=False,
            latency_ms=round((time.perf_counter() - started) * 1000),
            selected_tools=[],
            response_preview="",
            reason=f"timeout do provedor após {timeout_s:g}s",
        )
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
    timeout_s: float = 30.0,
) -> list[CapabilityEvalResult]:
    results: list[CapabilityEvalResult] = []
    for case in cases:
        case_schemas = schema_selector(case.prompt) if schema_selector else schemas
        results.append(await evaluate_case(
            backend, model, system_prompt, case_schemas, registry, case, timeout_s
        ))
    return results


async def evaluate_provider(
    provider: str,
    backend: LLMBackend,
    model: str,
    system_prompt: str,
    schemas: list[dict[str, Any]],
    registry: Any,
    *,
    runs: int = 1,
    schema_selector: Any | None = None,
    timeout_s: float = 30.0,
) -> ProviderEvalReport:
    """Executa a mesma suíte várias vezes e agrega consistência/latência."""
    if runs < 1:
        raise ValueError("runs deve ser pelo menos 1")
    all_results: list[CapabilityEvalResult] = []
    per_case: dict[str, list[bool]] = {case.name: [] for case in DEFAULT_CASES}
    for _ in range(runs):
        batch = await evaluate_suite(
            backend,
            model,
            system_prompt,
            schemas,
            registry,
            schema_selector=schema_selector,
            timeout_s=timeout_s,
        )
        all_results.extend(batch)
        for result in batch:
            per_case[result.name].append(result.passed)
    latencies = [result.latency_ms for result in all_results]
    failures: dict[str, int] = {}
    for result in all_results:
        if result.passed:
            continue
        reason = result.reason.casefold()
        category = (
            "rate_limit" if ("429" in reason or "quota" in reason)
            else "unavailable" if "503" in reason
            else "timeout" if "timeout" in reason
            else "provider_error" if "erro do provedor" in reason
            else "wrong_decision"
        )
        failures[category] = failures.get(category, 0) + 1
    return ProviderEvalReport(
        provider=provider,
        model=model,
        runs=runs,
        passed=sum(result.passed for result in all_results),
        total=len(all_results),
        average_latency_ms=round(statistics.fmean(latencies)) if latencies else 0,
        consistency={
            name: f"{sum(values)}/{len(values)}" for name, values in per_case.items()
        },
        failure_reasons=failures,
        results=all_results,
    )


async def _run_cli(
    model: str | None, provider: str, runs: int, timeout_s: float, as_json: bool
) -> int:
    from aila.core.config import get_settings
    from aila.core.engine import build_engine
    from aila.llm.registry import get_backend

    settings = get_settings()
    settings.memory.enabled = False
    backend = get_backend(settings.llm)
    engine = build_engine(settings, backend)
    available: dict[str, LLMBackend] = {"local": backend}
    available.update({
        name: candidate for name, candidate in engine.router.providers.items()
        if candidate is not backend
    })
    requested = list(available) if provider == "all" else [provider]
    missing = [name for name in requested if name not in available]
    if missing:
        configured = ", ".join(available)
        raise SystemExit(
            f"Provedor indisponível: {', '.join(missing)}. Disponíveis: {configured}"
        )
    reports: list[ProviderEvalReport] = []
    try:
        from aila.core.turn import _classify_task, select_tool_schemas

        def schemas_for(prompt: str) -> list[dict[str, Any]]:
            task, use_tools = _classify_task(prompt, "auto")
            if not use_tools:
                return []
            return select_tool_schemas(engine.agents.registry, task, prompt)

        for name in requested:
            candidate = available[name]
            selected_model = (
                model if name == "local" and model else candidate.default_model
            )
            reports.append(await evaluate_provider(
                name,
                candidate,
                selected_model,
                EVAL_SYSTEM_PROMPT,
                engine.agents.registry.schemas(),
                engine.agents.registry,
                runs=runs,
                schema_selector=schemas_for,
                timeout_s=timeout_s,
            ))
    finally:
        closed: set[int] = set()
        for candidate in available.values():
            if id(candidate) not in closed:
                closed.add(id(candidate))
                await candidate.aclose()

    payload = {"runs": runs, "providers": [asdict(report) for report in reports]}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Comparação de capacidades — {runs} rodada(s) por provedor")
        for report in reports:
            print(
                f"\n{report.provider} · {report.model}: "
                f"{report.passed}/{report.total} · média {report.average_latency_ms} ms"
            )
            if report.failure_reasons:
                summary = ", ".join(
                    f"{name}={count}" for name, count in report.failure_reasons.items()
                )
                print(f"  falhas: {summary}")
            for case, score in report.consistency.items():
                case_results = [r for r in report.results if r.name == case]
                avg = round(statistics.fmean(r.latency_ms for r in case_results))
                tools = sorted({tool for r in case_results for tool in r.selected_tools})
                print(f"  {case}: {score} · {avg} ms · {', '.join(tools) or 'sem tool'}")
    return 0 if all(report.passed == report.total for report in reports) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia as decisões de ferramentas de um modelo")
    parser.add_argument("--model", help="Modelo do Ollama; padrão: modelo configurado")
    parser.add_argument(
        "--provider", choices=("local", "gemini", "nvidia", "all"), default="local",
        help="Provedor a avaliar; padrão: local",
    )
    parser.add_argument("--runs", type=int, default=1, help="Rodadas por provedor")
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="Limite em segundos por caso"
    )
    parser.add_argument("--json", action="store_true", help="Emite relatório JSON")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(
        _run_cli(args.model, args.provider, args.runs, args.timeout, args.json)
    ))


if __name__ == "__main__":
    main()
