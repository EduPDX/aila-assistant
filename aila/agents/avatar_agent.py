"""Avatar Agent — deixa a Aila controlar o corpo do avatar 3D (VRM).

A IA pode acionar gestos pelo nome (ex.: "levante a mão" -> avatar.gesture
'raise_right'). O gesto é enviado à interface, que o aplica sobre o esqueleto
humanoid do VRM (padronizado, funciona em qualquer modelo).

O comando chega à UI por um evento ``avatar.gesture`` (ver engine/websocket).
Como é apenas uma animação (não toca no sistema do usuário), não passa por
confirmação de permissão.
"""

from __future__ import annotations

from aila.agents.base import BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("avatar_agent")

# gestos disponíveis (devem existir na biblioteca POSES do ui/avatar3d.html)
GESTURES = [
    "wave", "raise_right", "raise_left", "raise_both", "thumbs_up", "point",
    "hand_explain", "shrug", "think", "cheer", "rest",
]


class AvatarAgent(BaseAgent):
    name = "avatar"
    description = (
        "Controla o corpo do avatar 3D: aciona gestos como acenar, levantar a "
        "mão, apontar, dar joinha, pensar (mão no queixo), comemorar. Use quando "
        "o usuário pedir um movimento ou quando um gesto tornar a resposta mais viva."
    )

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="avatar.gesture",
                description=(
                    "Faz o avatar executar um gesto corporal. Nomes válidos: "
                    + ", ".join(GESTURES)
                ),
                params=[
                    ToolParam("name", "string", "Nome do gesto", enum=GESTURES),
                ],
                handler=self._gesture,
                agent=self.name,
            ),
            Tool(
                name="avatar.list_gestures",
                description="Lista os gestos que o avatar sabe fazer.",
                params=[],
                handler=self._list,
                agent=self.name,
            ),
        ]

    async def _gesture(self, args: dict) -> ToolResult:
        name = str(args.get("name", "")).strip()
        if name not in GESTURES:
            return ToolResult.error(
                f"Gesto desconhecido: '{name}'. Válidos: {', '.join(GESTURES)}"
            )
        sink = getattr(self.deps, "gesture_sink", None)
        if sink is None:
            return ToolResult.error("Controle de avatar indisponível.")
        sink(name)
        return ToolResult.success(f"Avatar executando: {name}")

    async def _list(self, args: dict) -> ToolResult:
        return ToolResult.success(", ".join(GESTURES))
