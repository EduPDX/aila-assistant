"""Benchmark da "escada" de modelos — medir do real, neste PC.

Resource Intelligence R12 (fecho da frente). Todo o resto MEDE em runtime; aqui a
Aila tira uma foto DELIBERADA: para cada modelo configurado, roda um prompt curto
e anota footprint (VRAM quente), latência até o 1º token (TTFT) e throughput
(tokens/s). O resultado é a ESCADA — modelos ordenados por custo de VRAM — que
dá números de referência p/ dimensionar presets e conferir as decisões de R5/R6/R9
contra a realidade da máquina, em vez de constantes chutadas.

kimi-k3-in-c em espírito: presets nascem de uma escada MEDIDA, não adivinhada.

Fora do hot-path: roda sob demanda (`python -m aila.core.benchmark`). Tolerante a
tudo — Ollama offline / modelo ausente → a amostra vira `ok=False` com o erro, e o
relatório segue. Não decide nada: só produz números.
"""

from __future__ import annotations

import contextlib
import json
import time
from dataclasses import asdict, dataclass, field

from aila.core.logging import get_logger

log = get_logger("benchmark")

_PROMPT = "Responda apenas com a palavra: ok."


@dataclass(slots=True)
class BenchSample:
    """Uma medição de um modelo. `ok=False` guarda o motivo em `error`."""

    model: str
    ok: bool = False
    ttft_ms: float = 0.0       # latência até o 1º token
    tps: float = 0.0           # throughput (tokens/s)
    gen_ms: float = 0.0        # tempo total da geração
    footprint_mb: int = 0      # VRAM quente após carregar (0 se desconhecido)
    error: str = ""


@dataclass(slots=True)
class BenchReport:
    """Foto do benchmark: as amostras + o hardware onde rodou. Serializável."""

    samples: list[BenchSample] = field(default_factory=list)
    gpu: str = ""

    def ladder(self) -> list[BenchSample]:
        """A ESCADA: só os modelos que responderam, do mais leve ao mais pesado
        (por footprint). É a base p/ dimensionar presets/rotas do real."""
        return sorted((s for s in self.samples if s.ok), key=lambda s: s.footprint_mb)

    def to_dict(self) -> dict:
        return {
            "gpu": self.gpu,
            "samples": [asdict(s) for s in self.samples],
            "ladder": [s.model for s in self.ladder()],
        }


async def benchmark_model(
    backend, model: str, *, prompt: str = _PROMPT, max_tokens: int = 32,
) -> BenchSample:
    """Roda UM prompt curto e mede TTFT/tps/tempo. Nunca levanta: falha do provedor
    (offline, modelo ausente) vira `ok=False` com o erro."""
    t0 = time.monotonic()
    ttft_ms = 0.0
    got: list[str] = []
    try:
        async for ch in backend.chat(
            [{"role": "user", "content": prompt}],
            stream=True, model=model, max_tokens=max_tokens,
        ):
            if ch.content:
                if not ttft_ms:
                    ttft_ms = (time.monotonic() - t0) * 1000
                got.append(ch.content)
    except Exception as exc:  # noqa: BLE001 - benchmark nunca derruba nada
        return BenchSample(model, ok=False, error=repr(exc))
    gen_ms = (time.monotonic() - t0) * 1000
    return BenchSample(
        model,
        ok=bool("".join(got).strip()),
        ttft_ms=round(ttft_ms, 1),
        tps=round(getattr(backend, "last_tps", 0.0) or 0.0, 1),
        gen_ms=round(gen_ms, 1),
    )


async def run_benchmark(
    backend, models: list[str], *, base_url: str = "http://127.0.0.1:11434",
    prompt: str = _PROMPT, max_tokens: int = 32,
) -> BenchReport:
    """Benchmarka cada modelo em série e mede o footprint quente (via ModelManager).
    Série de propósito: rodar em paralelo disputaria a mesma VRAM e falsearia tudo."""
    from aila.core.hardware import monitor
    from aila.core.models import ModelManager

    gpu = monitor.gpu()
    samples: list[BenchSample] = []
    for m in models:
        s = await benchmark_model(backend, m, prompt=prompt, max_tokens=max_tokens)
        if s.ok:                                    # footprint = VRAM quente agora
            st = (await ModelManager({"t": m}, base_url).inventory()).by_role("t")
            if st and st.loaded:
                s.footprint_mb = st.vram_mb
        log.info(f"bench {m}: ok={s.ok} tps={s.tps} ttft={s.ttft_ms}ms "
                 f"vram={s.footprint_mb}MB {s.error}")
        samples.append(s)
    return BenchReport(samples=samples, gpu=gpu.name if gpu else "")


def _benchmarkable(roles: dict[str, str]) -> list[str]:
    """Modelos únicos que fazem CHAT — exclui o papel 'embed' (embeddings não
    respondem /api/chat; benchmarká-los só geraria um erro garantido)."""
    return list(dict.fromkeys(m for r, m in roles.items() if r != "embed"))


def _cache_path():
    """Onde a escada medida fica guardada (data/, gitignored)."""
    from aila.core.config import data_path

    return data_path("benchmark.json")


def load_cached() -> dict | None:
    """Último relatório salvo (p/ a UI/`/api/resources`). None se não houver."""
    p = _cache_path()
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _save(report: BenchReport, models_sig: str) -> None:
    data = report.to_dict()
    data["ts"] = time.time()            # quando mediu (p/ o cache envelhecer)
    data["models_sig"] = models_sig     # conjunto de modelos coberto
    with contextlib.suppress(OSError):
        _cache_path().write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def boot_benchmark(backend, settings, *, max_age_days: float = 7.0) -> BenchReport | None:
    """Benchmark no BOOT, em background e com cache: só roda de fato se o cache
    estiver velho (> `max_age_days`) ou cobrir modelos diferentes — e nunca sob
    pressão alta (não disputa VRAM com o que o usuário está fazendo). Devolve o
    relatório quando roda, ou None quando pula. Nunca levanta."""
    from aila.core.models import roles_from_settings
    from aila.core.resources import Pressure, resources

    models = _benchmarkable(roles_from_settings(settings))
    sig = ",".join(models)

    cached = load_cached()
    if cached and cached.get("models_sig") == sig:
        age_days = (time.time() - cached.get("ts", 0)) / 86400
        if age_days < max_age_days:
            log.info(f"benchmark: cache fresco ({age_days:.1f}d < {max_age_days}d) — pulando")
            return None

    with contextlib.suppress(Exception):        # sob pressão, adia p/ o próximo boot
        if resources.snapshot().pressure >= Pressure.HIGH:
            log.info("benchmark: pressão alta no boot — adiado")
            return None

    log.info(f"benchmark: medindo a escada de {len(models)} modelo(s) em background…")
    report = await run_benchmark(backend, models, base_url=settings.llm.base_url)
    _save(report, sig)
    log.info(f"benchmark: escada salva — {report.to_dict()['ladder']}")
    return report


def _main() -> None:
    """CLI: `python -m aila.core.benchmark` — mede os modelos configurados e imprime
    o relatório (JSON). Fora do hot-path; seguro rodar quando quiser calibrar."""
    import asyncio

    from aila.core.config import get_settings
    from aila.core.models import roles_from_settings
    from aila.llm.registry import get_backend

    s = get_settings()
    backend = get_backend(s.llm)
    models = _benchmarkable(roles_from_settings(s))     # só modelos de chat, únicos
    report = asyncio.run(run_benchmark(backend, models, base_url=s.llm.base_url))
    _save(report, ",".join(models))     # atualiza o cache que a aba Recursos lê
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
