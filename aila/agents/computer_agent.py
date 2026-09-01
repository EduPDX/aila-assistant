"""Computer Agent — controle do computador (mouse, teclado, janelas, comandos).

⚠️  FASE 2. Este agente controla o SO real e é potencialmente perigoso.
Segurança em profundidade:
    - **Desabilitado por padrão** (habilite em ``config → agents.enabled``).
    - Toda atuação (mouse/teclado/comando) é ação de escrita: bloqueada no
      **modo somente-leitura**.
    - Ações destrutivas (`computer.mouse`, `computer.keyboard`,
      `computer.run_command`, `computer.open_app`) exigem **confirmação**.
    - Tudo é registrado no **log de auditoria**.
    - ``pyautogui.FAILSAFE``: leve o mouse ao canto superior-esquerdo p/ abortar.

Dependências opcionais::

    pip install -e ".[computer]"      # pyautogui, pygetwindow, pywin32

Ferramentas apenas-leitura (permitidas mesmo em modo somente-leitura, desde que
o agente esteja habilitado): screen_info, list_windows, cursor_position,
screenshot. Elas dão à IA "olhos" sobre a tela sem alterar nada.
"""

from __future__ import annotations

import asyncio
import subprocess

from aila.agents.base import BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("computer_agent")

# --- dependências opcionais (carregadas com tolerância a ausência) ---------- #
try:
    import pyautogui  # type: ignore

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _HAS_GUI = True
except Exception:  # noqa: BLE001
    pyautogui = None  # type: ignore
    _HAS_GUI = False

try:
    import pygetwindow as gw  # type: ignore

    _HAS_WIN = True
except Exception:  # noqa: BLE001
    gw = None  # type: ignore
    _HAS_WIN = False


def _need_gui() -> ToolResult | None:
    if not _HAS_GUI:
        return ToolResult.error(
            'Controle de mouse/teclado indisponível. Instale: pip install -e ".[computer]"'
        )
    return None


class ComputerAgent(BaseAgent):
    name = "computer"
    description = (
        "Controla o computador: ver a tela, listar/focar janelas, mover e clicar "
        "o mouse, digitar, atalhos de teclado, abrir programas e executar comandos. "
        "Atuação exige confirmação."
    )

    def tools(self) -> list[Tool]:
        return [
            # -------------------- LEITURA (percepção) -------------------- #
            Tool(
                name="computer.screen_info",
                description="Retorna a resolução da tela (largura x altura).",
                params=[],
                handler=self._screen_info,
                agent=self.name,
            ),
            Tool(
                name="computer.list_windows",
                description="Lista os títulos das janelas abertas.",
                params=[],
                handler=self._list_windows,
                agent=self.name,
            ),
            Tool(
                name="computer.cursor_position",
                description="Retorna a posição atual do cursor do mouse.",
                params=[],
                handler=self._cursor_position,
                agent=self.name,
            ),
            Tool(
                name="computer.screenshot",
                description="Captura a tela e salva um PNG no workspace.",
                params=[
                    ToolParam("path", "string", "Nome do arquivo (ex.: tela.png)",
                              required=False)
                ],
                handler=self._screenshot,
                agent=self.name,
            ),
            # -------------------- ATUAÇÃO (escrita) ---------------------- #
            Tool(
                name="computer.focus_window",
                description="Traz uma janela para frente pelo título (parcial).",
                params=[ToolParam("title", "string", "Trecho do título da janela")],
                handler=self._focus_window,
                agent=self.name,
            ),
            Tool(
                name="computer.move_mouse",
                description="Move o cursor para (x, y).",
                params=[
                    ToolParam("x", "integer", "Coordenada X"),
                    ToolParam("y", "integer", "Coordenada Y"),
                ],
                handler=self._move_mouse,
                agent=self.name,
            ),
            Tool(
                name="computer.click",
                description="Clica o mouse (em x,y se informado; senão na posição atual).",
                params=[
                    ToolParam("x", "integer", "Coordenada X", required=False),
                    ToolParam("y", "integer", "Coordenada Y", required=False),
                    ToolParam("button", "string", "left|right|middle", required=False,
                              enum=["left", "right", "middle"]),
                    ToolParam("double", "boolean", "Clique duplo?", required=False),
                ],
                handler=self._click,
                agent=self.name,
            ),
            Tool(
                name="computer.type",
                description="Digita um texto via teclado virtual.",
                params=[ToolParam("text", "string", "Texto a digitar")],
                handler=self._type,
                agent=self.name,
            ),
            Tool(
                name="computer.hotkey",
                description="Pressiona uma combinação de teclas (ex.: ctrl+c, alt+tab).",
                params=[ToolParam("keys", "string", "Teclas separadas por '+'")],
                handler=self._hotkey,
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
                name="computer.run_command",
                description="Executa um comando no PowerShell e retorna a saída.",
                params=[ToolParam("command", "string", "Comando a executar")],
                handler=self._run_command,
                agent=self.name,
            ),
        ]

    # ============================ LEITURA ============================== #
    async def _screen_info(self, args: dict) -> ToolResult:
        await self.authorize("computer.screen.info", args)
        if err := _need_gui():
            return err
        w, h = pyautogui.size()
        return ToolResult.success(f"Resolução: {w}x{h}", width=w, height=h)

    async def _list_windows(self, args: dict) -> ToolResult:
        await self.authorize("computer.window.list", args)
        if not _HAS_WIN:
            return ToolResult.error(
                'Gerência de janelas indisponível. Instale: pip install -e ".[computer]"'
            )
        titles = [t for t in gw.getAllTitles() if t.strip()]
        return ToolResult.success("\n".join(titles) or "(nenhuma)", count=len(titles))

    async def _cursor_position(self, args: dict) -> ToolResult:
        await self.authorize("computer.cursor.get", args)
        if err := _need_gui():
            return err
        p = pyautogui.position()
        return ToolResult.success(f"Cursor em ({p.x}, {p.y})", x=p.x, y=p.y)

    async def _screenshot(self, args: dict) -> ToolResult:
        await self.authorize("computer.screenshot.get", args)
        rel = args.get("path") or "tela.png"
        dest = self.deps.sandbox.resolve(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Usa mss (leve, sem Pillow); cai para pyautogui se mss não existir.
        try:
            import mss  # type: ignore
            import mss.tools  # type: ignore

            with mss.mss() as sct:
                sct.shot(mon=-1, output=str(dest))
        except Exception:  # noqa: BLE001
            if not _HAS_GUI:
                return ToolResult.error(
                    'Captura indisponível. Instale: pip install -e ".[computer]"'
                )
            try:
                pyautogui.screenshot().save(str(dest))
            except Exception as exc:  # noqa: BLE001
                return ToolResult.error(f"Falha na captura: {exc}")
        return ToolResult.success(f"Screenshot salvo em {rel}", path=str(dest))

    # ============================ ATUAÇÃO ============================== #
    async def _focus_window(self, args: dict) -> ToolResult:
        await self.authorize("computer.window.focus", args)  # escrita (bloqueia em RO)
        if not _HAS_WIN:
            return ToolResult.error('Instale: pip install -e ".[computer]"')
        matches = gw.getWindowsWithTitle(args["title"])
        if not matches:
            return ToolResult.error(f"Nenhuma janela com título ~ '{args['title']}'")
        win = matches[0]
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Falha ao focar janela: {exc}")
        return ToolResult.success(f"Janela em foco: {win.title}")

    async def _move_mouse(self, args: dict) -> ToolResult:
        await self.authorize("computer.mouse", args)
        if err := _need_gui():
            return err
        pyautogui.moveTo(int(args["x"]), int(args["y"]), duration=0.2)
        return ToolResult.success(f"Cursor movido para ({args['x']}, {args['y']})")

    async def _click(self, args: dict) -> ToolResult:
        await self.authorize("computer.mouse", args)
        if err := _need_gui():
            return err
        button = args.get("button", "left")
        clicks = 2 if args.get("double") else 1
        if args.get("x") is not None and args.get("y") is not None:
            pyautogui.click(int(args["x"]), int(args["y"]), clicks=clicks, button=button)
        else:
            pyautogui.click(clicks=clicks, button=button)
        return ToolResult.success(f"Clique {button} x{clicks} executado.")

    async def _type(self, args: dict) -> ToolResult:
        await self.authorize("computer.keyboard", args)
        if err := _need_gui():
            return err
        text = args["text"]
        # pyautogui.typewrite só suporta ASCII; para texto com acentos (pt-BR),
        # usamos clipboard + Ctrl+V que funciona com qualquer Unicode.
        if any(ord(c) > 127 for c in text):
            try:
                import pyperclip
            except ImportError:
                return ToolResult.error(
                    'Clipboard Unicode indisponível. Instale: pip install "pyperclip"'
                )
            try:
                pyperclip.copy(text)
            except pyperclip.PyperclipException as exc:
                return ToolResult.error(f"Clipboard Unicode indisponível: {exc}")
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.typewrite(text, interval=0.02)
        return ToolResult.success("Texto digitado.")

    async def _hotkey(self, args: dict) -> ToolResult:
        await self.authorize("computer.keyboard", args)
        if err := _need_gui():
            return err
        keys = [k.strip().lower() for k in args["keys"].split("+") if k.strip()]
        if not keys:
            return ToolResult.error("Nenhuma tecla informada.")
        pyautogui.hotkey(*keys)
        return ToolResult.success(f"Atalho pressionado: {'+'.join(keys)}")

    async def _open_app(self, args: dict) -> ToolResult:
        await self.authorize("computer.open_app", args)
        app = args["app"]
        # CommandGuard: bloqueia apps que podem ser usados para bypass de segurança
        # (ex.: abrir powershell/cmd diretamente ignora o filter de run_command).
        blocked_apps = {"powershell", "pwsh", "cmd", "wt", "wsl", "bash", "sh"}
        if app.lower().split("/")[-1].split("\\")[-1].split(".")[0] in blocked_apps:
            return ToolResult.error(
                f"App bloqueado pelo CommandGuard: {app}. "
                "Use run_command() para executar comandos."
            )
        try:
            subprocess.Popen(["cmd", "/c", "start", "", app], shell=False)
        except OSError as exc:
            return ToolResult.error(f"Falha ao abrir '{app}': {exc}")
        return ToolResult.success(f"Solicitado abrir: {app}")

    async def _run_command(self, args: dict) -> ToolResult:
        command = (args.get("command") or "").strip()
        # Guard de terminal (defesa em profundidade): comandos catastróficos são
        # BLOQUEADOS antes de qualquer confirmação/autorização.
        from aila.security.command_guard import CommandGuard

        blocked, why = CommandGuard(self.deps.settings.security).is_blocked(command)
        if blocked:
            self.deps.permissions.audit.record(
                "computer.run_command", self.name, {"command": command[:200]},
                f"blocked: {why}", allowed=False,
            )
            return ToolResult.error(
                f"Comando BLOQUEADO por segurança ({why}). Se for realmente "
                "necessário, o usuário deve executá-lo manualmente."
            )
        await self.authorize("computer.run_command", args)
        try:
            # em THREAD: subprocess.run direto no handler async travaria o event
            # loop por até 60s (avatar/WebSocket congelados durante o comando).
            proc = await asyncio.to_thread(
                lambda: subprocess.run(  # noqa: S603
                    ["powershell", "-NoProfile", "-Command", args["command"]],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            )
        except subprocess.TimeoutExpired:
            return ToolResult.error("Comando excedeu o tempo limite (60s).")
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return ToolResult.error(
                f"Comando falhou (código {proc.returncode}): "
                f"{out.strip()[:4000] or '(sem saída)'}"
            )
        return ToolResult.success(out.strip() or "(sem saída)", returncode=proc.returncode)
