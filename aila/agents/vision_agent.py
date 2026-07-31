"""Vision Agent — análise de imagens, screenshots e interfaces.

⚠️  FASE 3. Usa um modelo multimodal (LLaVA / Qwen-VL) servido pelo Ollama.
A captura de tela requer o extra ``vision`` (mss + pillow).
"""

from __future__ import annotations

import base64
from pathlib import Path

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("vision_agent")


class VisionAgent(BaseAgent):
    name = "vision"
    description = "Analisa imagens e screenshots, interpretando interfaces e conteúdo visual."

    def __init__(self, deps: AgentDeps) -> None:
        super().__init__(deps)
        self.vision_model = deps.settings.llm.vision_model

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="vision.analyze_image",
                description="Descreve/analisa uma imagem do workspace.",
                params=[
                    ToolParam("path", "string", "Caminho da imagem no workspace"),
                    ToolParam("question", "string", "O que analisar", required=False),
                ],
                handler=self._analyze,
                agent=self.name,
            ),
            Tool(
                name="vision.screenshot_analyze",
                description="Captura a tela e a interpreta (requer extra 'vision').",
                params=[ToolParam("question", "string", "O que procurar", required=False)],
                handler=self._screenshot,
                agent=self.name,
            ),
        ]

    async def _describe(self, image_b64: str, question: str) -> str:
        """Envia imagem+pergunta ao modelo multimodal via Ollama.

        O backend Ollama aceita imagens no campo ``images`` da mensagem.
        """
        messages = [
            {
                "role": "user",
                "content": question or "Descreva esta imagem em detalhes.",
                "images": [image_b64],
            }
        ]
        return await self.deps.llm.complete(messages, model=self.vision_model)

    async def _analyze(self, args: dict) -> ToolResult:
        await self.authorize("vision.analyze_image", args)
        path = self.deps.sandbox.resolve(args["path"])
        if not path.is_file():
            return ToolResult.error(f"Imagem não encontrada: {args['path']}")
        b64 = base64.b64encode(Path(path).read_bytes()).decode()
        out = await self._describe(b64, args.get("question", ""))
        return ToolResult.success(out)

    async def _screenshot(self, args: dict) -> ToolResult:
        await self.authorize("vision.analyze_image", args)
        try:
            import mss  # type: ignore
        except Exception:  # noqa: BLE001
            return ToolResult.error(
                "Captura indisponível. Instale: pip install -e \".[vision]\""
            )
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            import mss.tools  # type: ignore

            png = mss.tools.to_png(shot.rgb, shot.size)
        b64 = base64.b64encode(png).decode()
        out = await self._describe(b64, args.get("question", ""))
        return ToolResult.success(out)
