"""OOM prevention geral — decidir se um modelo CABE antes de carregá-lo.

Resource Intelligence R6. Antes existia só o pré-voo da VISÃO (`vision_agent.py`):
antes de trazer o 2º modelo (~5 GB) nos 8 GB, ele media a VRAM e encolhia o
avatar se o headroom fosse baixo. Isso vira aqui uma decisão GERAL e reusável:
`decide_load` (pura, testável) responde "cabe? o que fazer?" para QUALQUER modelo,
e `OomGuard.can_load` reúne os números reais — headroom via HardwareMonitor (R1) e
footprint estimado via ModelManager (R3, medindo do real quando o modelo já foi
carregado ou está instalado).

Ações possíveis (sem hard-refuse por ora — o comportamento seguro atual é liberar
VRAM e tentar, nunca bloquear o usuário):
  • proceed — cabe (ou já está carregado, ou não deu p/ medir): segue.
  • shrink  — headroom baixo: libere VRAM (encolher avatar / soltar o frio) antes.

Fronteira preservada (privacidade > recurso): faltar VRAM NUNCA vira envio p/ a
nuvem. A decisão aqui é só sobre o que fazer LOCALMENTE antes de carregar.
"""

from __future__ import annotations

from dataclasses import dataclass

from aila.core.logging import get_logger

log = get_logger("oom")

# Sobrecusto do disco→VRAM (pesos + KV/contexto). Um 7B Q4 ~4.7 GB em disco pesa
# ~5.2 GB carregado (medido no /api/ps) → ~1.15×.
_VRAM_OVERHEAD = 1.15
# Estimativa quando não dá p/ medir (modelo desconhecido/não instalado). Um 7B Q4
# ~5 GB — a mesma ordem do 2º modelo que motivou o pré-voo da visão.
_DEFAULT_FOOTPRINT_MB = 5000


@dataclass(slots=True)
class LoadDecision:
    """Veredito de pré-voo p/ carregar um modelo. Serializável p/ log/UI."""

    model: str
    need_mb: int              # footprint estimado do modelo em VRAM
    headroom_mb: int          # VRAM livre agora
    available: bool           # deu p/ medir a VRAM (nvidia-smi respondeu)?
    already_loaded: bool      # já está quente → carregar é no-op
    fits: bool                # cabe no headroom atual?
    action: str               # "proceed" | "shrink"
    reason: str

    def to_dict(self) -> dict:
        return {
            "model": self.model, "need_mb": self.need_mb,
            "headroom_mb": self.headroom_mb, "available": self.available,
            "already_loaded": self.already_loaded, "fits": self.fits,
            "action": self.action, "reason": self.reason,
        }


def decide_load(
    model: str,
    headroom_mb: int,
    available: bool,
    *,
    need_mb: int,
    already_loaded: bool = False,
) -> LoadDecision:
    """Decisão PURA de pré-voo (sem I/O): dado o headroom e o footprint estimado,
    diz se cabe e o que fazer. Sem medição de VRAM ou modelo já quente → 'proceed'
    (não bloqueia com base no desconhecido)."""
    if not available:
        return LoadDecision(model, need_mb, headroom_mb, False, already_loaded,
                            True, "proceed", "sem medição de VRAM")
    if already_loaded:
        return LoadDecision(model, need_mb, headroom_mb, True, True,
                            True, "proceed", "modelo já carregado")
    fits = headroom_mb >= need_mb
    if fits:
        return LoadDecision(model, need_mb, headroom_mb, True, False,
                            True, "proceed", "cabe no headroom")
    return LoadDecision(model, need_mb, headroom_mb, True, False,
                        False, "shrink", "headroom baixo — liberar VRAM antes de carregar")


def _footprint_from_state(st) -> int:
    """Footprint estimado (MB) a partir do estado do modelo no inventário (R3).
    Mede do real quando dá: já carregado → size_vram; instalado → disco×overhead;
    desconhecido → estimativa default."""
    if st is not None:
        if st.loaded and st.vram_mb:
            return st.vram_mb
        if st.disk_mb:
            return int(st.disk_mb * _VRAM_OVERHEAD)
    return _DEFAULT_FOOTPRINT_MB


class OomGuard:
    """Reúne headroom (HardwareMonitor) + footprint (ModelManager) e decide via
    `decide_load`. Ponto único de pré-voo p/ qualquer carga de modelo."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url

    async def can_load(self, model: str, *, need_mb: int | None = None) -> LoadDecision:
        """Pré-voo de `model`: cabe no headroom atual? `need_mb` força o footprint
        (a visão usa isso); senão estima do inventário real."""
        from aila.core.hardware import monitor
        from aila.core.models import ModelManager

        r = await monitor.gpu_async()
        if r is None:
            return decide_load(model, 0, False,
                               need_mb=need_mb or _DEFAULT_FOOTPRINT_MB)
        # o modelo consultado entra como um "papel" temporário p/ o inventário puxar
        # seu tamanho em disco (/api/tags) e footprint quente (/api/ps).
        inv = await ModelManager({"target": model}, self.base_url).inventory()
        st = inv.by_role("target")
        already = bool(st and st.loaded)
        need = need_mb if need_mb is not None else _footprint_from_state(st)
        return decide_load(model, int(r.free_mb), True,
                           need_mb=need, already_loaded=already)
