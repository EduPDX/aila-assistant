"""Computer Agent — controle do computador (mouse, teclado, apps, comandos).

⚠️  FASE 2. Este agente controla o SO real e é potencialmente perigoso.
Toda ação aqui é destrutiva por definição e passa por confirmação + auditoria.

As dependências (pyautogui, pywin32) são opcionais::

    pip install -e ".[computer]"

Enquanto os extras não estiverem instalados, as tools respondem com uma
mensagem clara em vez de quebrar o sistema.
"""

from __future__ import annotations

import subprocess

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("computer_agent")

try:
    import pyautogui  # type: ignore

    pyautogui.FAILSAFE = True  # mover o mouse ao canto superior-esquerdo aborta
    _HAS_GUI = True
except Exception:  # noqa: BLE001
    _HAS_GUI = False


class ComputerAgent(BaseAgent):
    name = "computer"
    description = (
        "Controla o computador: executar comandos, abrir programas, mover o "
        "mouse e digitar. Requer confirmação para toda ação."
    )

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="computer.run_command",
                description="Executa um comando no PowerShell (destrutivo).",
                params=[ToolParam("command", "string", "Comando a executar")],
                handler=self._run_command,
                agent=self.name,
            ),
            Tool(
                name="computer.open_app",
                description="Abre um programa pelo nome/caminho.",
                params=[ToolParam("app", "string", "Executável ou nome do app")],
                handler=self._open_app,
                agent=self.name,
            ),
            Tool(
                name="computer.type",
                description="Digita um texto via teclado virtual (destrutivo).",
                params=[ToolParam("text", "string", "Texto a digitar")],
                handler=self._type,
                agent=self.name,
            ),
        ]

    # ------------------------------------------------------------------ #
    async def _run_command(self, args: dict) -> ToolResult:
        await self.authorize("computer.run_command", args)
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", args["command"]],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.error("Comando excedeu o tempo limite (60s).")
        out = (proc.stdout or "") + (proc.stderr or "")
        return ToolResult.success(out.strip() or "(sem saída)", returncode=proc.returncode)

    async def _open_app(self, args: dict) -> ToolResult:
        await self.authorize("computer.run_command", args)
        subprocess.Popen(["cmd", "/c", "start", "", args["app"]], shell=False)
        return ToolResult.success(f"Solicitado abrir: {args['app']}")

    async def _type(self, args: dict) -> ToolResult:
        await self.authorize("computer.keyboard", args)
        if not _HAS_GUI:
            return ToolResult.error(
                "Controle de teclado indisponível. Instale: pip install -e \".[computer]\""
            )
        pyautogui.typewrite(args["text"], interval=0.02)
        return ToolResult.success("Texto digitado.")
