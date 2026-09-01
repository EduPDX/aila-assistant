"""Vision Agent — análise de imagens, screenshots e interfaces.

FASE 3. Usa um modelo multimodal (LLaVA / Qwen-VL) servido pelo Ollama. O
Ollama aceita imagens em base64 no campo ``images`` da mensagem de chat.

Fecha o ciclo com o Computer Agent: ele captura a tela (`computer.screenshot`
ou `vision.screenshot_analyze`), o Vision Agent interpreta, e a IA decide a ação.

Requer o modelo baixado::

    ollama pull llava:7b        # ou qwen2.5vl:7b

Se o modelo não estiver disponível, as ferramentas retornam uma mensagem clara
em vez de quebrar.
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("vision_agent")

_DEFAULT_PROMPT = "Descreva esta imagem em detalhes, em português."
_UI_PROMPT = (
    "Você está vendo uma captura de tela de um computador. Descreva a interface: "
    "quais janelas/apps estão abertos, botões e campos visíveis, e onde estão "
    "(canto superior, centro, etc.). Seja objetivo e útil para automação."
)


class VisionAgent(BaseAgent):
    name = "vision"
    description = (
        "Analisa imagens e screenshots com um modelo multimodal (LLaVA): descreve "
        "conteúdo, lê texto e interpreta interfaces para ajudar a agir na tela."
    )

    def __init__(self, deps: AgentDeps) -> None:
        super().__init__(deps)
        self.vision_model = deps.settings.llm.vision_model

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="vision.analyze_image",
                description="Descreve/analisa uma imagem que está no workspace.",
                params=[
                    ToolParam("path", "string", "Caminho da imagem no workspace"),
                    ToolParam("question", "string", "O que analisar (opcional)",
                              required=False),
                ],
                handler=self._analyze,
                agent=self.name,
            ),
            Tool(
                name="vision.read_text",
                description="Lê/extrai o texto visível em uma imagem (OCR via modelo).",
                params=[ToolParam("path", "string", "Caminho da imagem no workspace")],
                handler=self._read_text,
                agent=self.name,
            ),
            Tool(
                name="vision.screenshot_analyze",
                description="Captura a tela agora e interpreta a interface visível.",
                params=[
                    ToolParam("question", "string", "O que procurar (opcional)",
                              required=False)
                ],
                handler=self._screenshot,
                agent=self.name,
            ),
        ]

    # ------------------------------------------------------------------ #
    async def _vram_preflight(self) -> None:
        """VRAM Fase 3: antes de carregar o modelo de VISÃO (2º modelo ~5 GB) nos
        8 GB, verifica se cabe. Se o headroom for baixo, encolhe o avatar
        PREVENTIVAMENTE (libera framebuffer) e avisa — em vez de deixar o WebGL
        cair no pico da carga (o bug 'pedi análise e o avatar sumiu'). O HUD
        reassume o estado real em ~2 s. No-op sem nvidia-smi; nunca quebra a visão."""
        try:
            from aila.core.event_bus import bus
            from aila.core.oom import decide_load
            from aila.core.vram import VISION_HEADROOM_MB, VramPlanner

            plan = await VramPlanner(self.deps.settings.llm.base_url).measure()
            # decisão de pré-voo COMPARTILHADA (R6): o modelo de visão precisa de
            # ~5 GB; se não couber no headroom, a ação é 'shrink' (liberar VRAM).
            decision = decide_load(
                self.vision_model, plan.headroom_mb, plan.available,
                need_mb=VISION_HEADROOM_MB,
            )
            if decision.action == "shrink":
                payload = plan.to_dict()
                payload["state"] = "red"            # encolhimento preventivo
                payload["reason"] = "vision-preload"
                await bus.emit("system.vram", payload, source="vision")
                log.warning(
                    f"VRAM apertada p/ o modelo de visão (livre {plan.headroom_mb} MB "
                    f"< {VISION_HEADROOM_MB}); avatar reduzido preventivamente."
                )
        except Exception as exc:  # noqa: BLE001 - preflight jamais derruba a visão
            log.debug(f"preflight de VRAM ignorado: {exc!r}")

    async def _describe(self, image_b64: str, prompt: str) -> ToolResult:
        """Envia imagem+pergunta ao modelo multimodal via Ollama."""
        messages = [{"role": "user", "content": prompt, "images": [image_b64]}]
        await self._vram_preflight()   # abre espaço na VRAM antes de carregar a visão
        try:
            out = await self.deps.llm.complete(messages, model=self.vision_model)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return ToolResult.error(
                    f"Modelo de visão '{self.vision_model}' não encontrado. "
                    f"Baixe com: ollama pull {self.vision_model}"
                )
            return ToolResult.error(f"Erro do modelo de visão: {exc}")
        except httpx.HTTPError as exc:
            return ToolResult.error(f"Falha ao contatar o modelo de visão: {exc}")
        return ToolResult.success(out.strip() or "(sem descrição)")

    def _encode_workspace_image(self, rel_path: str) -> tuple[str | None, str | None]:
        """Retorna (base64, erro). Valida sandbox e existência."""
        path = self.deps.sandbox.resolve(rel_path, read=True)   # lê pastas anexadas
        if not path.is_file():
            return None, f"Imagem não encontrada no workspace: {rel_path}"
        data = path.read_bytes()
        if len(data) > 20_000_000:
            return None, "Imagem muito grande (>20MB)."
        return base64.b64encode(data).decode(), None

    async def _analyze(self, args: dict) -> ToolResult:
        await self.authorize("vision.analyze", args)  # leitura (permitido em RO)
        b64, err = self._encode_workspace_image(args["path"])
        if err:
            return ToolResult.error(err)
        return await self._describe(b64, args.get("question") or _DEFAULT_PROMPT)

    async def _read_text(self, args: dict) -> ToolResult:
        await self.authorize("vision.read", args)  # leitura (permitido em RO)
        b64, err = self._encode_workspace_image(args["path"])
        if err:
            return ToolResult.error(err)
        prompt = (
            "Transcreva TODO o texto visível nesta imagem, preservando a ordem de "
            "leitura. Responda apenas com o texto, sem comentários."
        )
        return await self._describe(b64, prompt)

    async def _screenshot(self, args: dict) -> ToolResult:
        await self.authorize("vision.screenshot.get", args)
        try:
            import mss  # type: ignore
            import mss.tools  # type: ignore
        except Exception:  # noqa: BLE001
            return ToolResult.error(
                'Captura indisponível. Instale: pip install -e ".[vision]"'
            )
        # captura a tela e salva no workspace (fica inspecionável)
        dest = self.deps.sandbox.resolve("_screenshot_vision.png")
        with mss.mss() as sct:
            sct.shot(mon=-1, output=str(dest))
        b64 = base64.b64encode(Path(dest).read_bytes()).decode()
        prompt = args.get("question") or _UI_PROMPT
        result = await self._describe(b64, prompt)
        if result.data is None:
            result.data = {}
        result.data["path"] = str(dest)
        return result
