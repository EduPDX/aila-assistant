"""Code Agent — geração, análise e correção de código.

Usa um modelo especializado em código (ex.: deepseek-coder) via o mesmo
backend de LLM. Ele não executa código por padrão (isso é uma ação destrutiva
que exigirá o Computer Agent + confirmação numa fase futura).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.config import PROJECT_ROOT
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("code_agent")


def _find_python() -> str | None:
    """Acha o interpretador Python do sistema (no .exe, sys.executable é o
    próprio backend — então procuramos no PATH)."""
    for cand in ("python", "py", "python3"):
        exe = shutil.which(cand)
        if exe:
            return exe
    return None


def _venv_python() -> str | None:
    """Python do PROJETO (venv) — necessário p/ rodar os testes (tem as deps).
    Cai para o Python do sistema se não houver venv."""
    for rel in (Path(".venv") / "Scripts" / "python.exe", Path(".venv") / "bin" / "python"):
        cand = PROJECT_ROOT / rel
        if cand.exists():
            return str(cand)
    return _find_python()


def _repo_resolve(rel: str) -> Path | None:
    """Resolve um caminho DENTRO do repositório (bloqueia escapar do PROJECT_ROOT)."""
    root = PROJECT_ROOT.resolve()
    try:
        p = (root / rel).resolve()
    except (OSError, ValueError):
        return None
    return p if str(p).startswith(str(root)) else None


class CodeAgent(BaseAgent):
    name = "code"
    description = (
        "Escreve, explica, revisa, corrige e EXECUTA código. Use code.run para "
        "rodar um código Python e obter a saída real (pede confirmação)."
    )

    def __init__(self, deps: AgentDeps) -> None:
        super().__init__(deps)
        self.code_model = deps.settings.llm.code_model

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="code.generate",
                description="Gera código a partir de uma descrição.",
                params=[
                    ToolParam("task", "string", "O que o código deve fazer"),
                    ToolParam("language", "string", "Linguagem (ex.: python)", required=False),
                ],
                handler=self._generate,
                agent=self.name,
            ),
            Tool(
                name="code.analyze",
                description="Analisa um trecho de código e aponta problemas.",
                params=[ToolParam("code", "string", "Código a analisar")],
                handler=self._analyze,
                agent=self.name,
            ),
            Tool(
                name="code.fix",
                description="Corrige código a partir de uma mensagem de erro.",
                params=[
                    ToolParam("code", "string", "Código com problema"),
                    ToolParam("error", "string", "Mensagem de erro / comportamento"),
                ],
                handler=self._fix,
                agent=self.name,
            ),
            Tool(
                name="code.run",
                description=(
                    "Executa um código PYTHON e retorna a saída real (stdout/erro). "
                    "Use quando o usuário pedir para RODAR/EXECUTAR um código. "
                    "Não use input() — passe valores fixos no próprio código."
                ),
                params=[ToolParam("code", "string", "Código Python a executar")],
                handler=self._run,
                agent=self.name,
            ),
            Tool(
                name="code.test",
                description="Roda a suíte de testes do projeto (pytest) e devolve o resultado.",
                params=[ToolParam("path", "string", "arquivo/pasta de teste", required=False)],
                handler=self._test,
                agent=self.name,
            ),
            Tool(
                name="code.read_file",
                description="Lê um arquivo do repositório do projeto (caminho relativo à raiz).",
                params=[ToolParam("path", "string", "ex.: aila/core/engine.py")],
                handler=self._read_file,
                agent=self.name,
            ),
            Tool(
                name="code.write_file",
                description=(
                    "ESCREVE um arquivo no repositório (auto-modificação; faz backup .bak). "
                    "Exige autonomia L5 (self-improve)."
                ),
                params=[
                    ToolParam("path", "string", "caminho relativo à raiz do repo"),
                    ToolParam("content", "string", "novo conteúdo completo do arquivo"),
                ],
                handler=self._write_file,
                agent=self.name,
            ),
        ]

    # ------------------------------------------------------------------ #
    async def _ask_code_model(self, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return await self.deps.llm.complete(messages, model=self.code_model)

    async def _generate(self, args: dict) -> ToolResult:
        await self.authorize("code.generate", args)
        lang = args.get("language", "python")
        out = await self._ask_code_model(
            f"Você é um engenheiro de software sênior. Escreva código {lang} "
            "limpo, idiomático e comentado. Responda apenas com o código.",
            args["task"],
        )
        return ToolResult.success(out, language=lang)

    async def _analyze(self, args: dict) -> ToolResult:
        await self.authorize("code.analyze", args)
        out = await self._ask_code_model(
            "Você é um revisor de código rigoroso. Aponte bugs, riscos de "
            "segurança e melhorias, em tópicos objetivos.",
            args["code"],
        )
        return ToolResult.success(out)

    async def _fix(self, args: dict) -> ToolResult:
        await self.authorize("code.fix", args)
        out = await self._ask_code_model(
            "Você conserta código. Explique brevemente a causa e devolva a "
            "versão corrigida completa.",
            f"CÓDIGO:\n{args['code']}\n\nERRO:\n{args['error']}",
        )
        return ToolResult.success(out)

    async def _run(self, args: dict) -> ToolResult:
        await self.authorize("code.execute", args)  # destrutiva -> confirmação
        code = (args.get("code") or "").strip()
        if not code:
            return ToolResult.error("Nenhum código para executar.")
        exe = _find_python()
        if not exe:
            return ToolResult.error(
                "Python não encontrado no PATH deste computador. Instale o Python "
                "(python.org) para executar código."
            )
        path = self.deps.sandbox.resolve("_aila_run.py")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [exe, str(path)],
                capture_output=True, text=True, timeout=30,
                stdin=subprocess.DEVNULL,  # input() falha rápido em vez de travar
            )
        except subprocess.TimeoutExpired:
            return ToolResult.error("Execução excedeu o tempo limite (30s).")
        finally:
            path.unlink(missing_ok=True)
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return ToolResult.success(out or "(sem saída)", returncode=proc.returncode)

    async def _test(self, args: dict) -> ToolResult:
        await self.authorize("code.test", args)   # roda a suíte (L3; sem confirmar a cada run)
        exe = _venv_python()   # precisa do Python do projeto (com as deps)
        if not exe:
            return ToolResult.error("Python não encontrado (venv/PATH).")
        target = args.get("path") or "tests"
        try:
            proc = subprocess.run(
                [exe, "-m", "pytest", "-q", "--no-header", target],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.error("Testes excederam o tempo limite (180s).")
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        passed = proc.returncode == 0
        tail = out[-1500:]
        return ToolResult.success(
            f"{'✓ PASSOU' if passed else '✗ FALHOU'}\n{tail}",
            passed=passed, returncode=proc.returncode,
        )

    async def _read_file(self, args: dict) -> ToolResult:
        await self.authorize("code.read", args)      # leitura → SAFE
        p = _repo_resolve(args["path"])
        if p is None or not p.is_file():
            return ToolResult.error(f"Arquivo não encontrado no repo: {args['path']}")
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult.error(f"Falha ao ler: {exc}")
        return ToolResult.success(text[:20000], path=args["path"])

    async def _write_file(self, args: dict) -> ToolResult:
        # auto-modificação do próprio código → gate de autonomia L5 (self-improve)
        await self.authorize("code.write", args)
        p = _repo_resolve(args["path"])
        if p is None:
            return ToolResult.error("Caminho fora do repositório.")
        content = args.get("content", "")
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():                                # backup .bak antes de sobrescrever
            try:
                shutil.copyfile(p, p.with_suffix(p.suffix + ".bak"))
            except OSError:
                pass
        try:
            p.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult.error(f"Falha ao escrever: {exc}")
        self.deps.permissions.audit.record(
            "code.write", self.name, {"path": args["path"], "bytes": len(content)},
            "written", allowed=True,
        )
        return ToolResult.success(f"Escrito {args['path']} ({len(content)} bytes; backup .bak).")
