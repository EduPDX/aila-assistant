"""Git Agent — operações git no repositório do projeto.

A base do "trabalhar no próprio código com segurança": inspeção (status/diff/
log), branches de backup/experimento e rollback (checkout). Opera no
PROJECT_ROOT (o repo), não no sandbox do workspace. Leituras são SAFE; escritas
(branch/commit/checkout) passam pelo gate de permissão/autonomia.
"""

from __future__ import annotations

import asyncio
import subprocess

from aila.agents.base import BaseAgent
from aila.core.config import PROJECT_ROOT
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("git_agent")


def _git(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=timeout,
    )


async def _git_async(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Git sem bloquear o WebSocket/avatar durante operações lentas."""
    return await asyncio.to_thread(_git, *args, timeout=timeout)


class GitAgent(BaseAgent):
    name = "git"
    description = (
        "Git no repositório do projeto: ver estado/diff/log (leitura), criar "
        "branch de backup, trocar de branch (rollback) e commitar."
    )

    def tools(self) -> list[Tool]:
        return [
            Tool("git.status", "Arquivos modificados no repositório.", [],
                 self._status, self.name),
            Tool("git.diff", "Diff das mudanças (opcional: caminho).",
                 [ToolParam("path", "string", "arquivo/pasta", required=False)],
                 self._diff, self.name),
            Tool("git.log", "Últimos commits.",
                 [ToolParam("n", "integer", "quantos (padrão 10)", required=False)],
                 self._log, self.name),
            Tool("git.current_branch", "Nome da branch atual.", [],
                 self._current, self.name),
            Tool("git.branch_create", "Cria e entra numa branch (backup/experimento).",
                 [ToolParam("name", "string", "nome da branch")],
                 self._branch_create, self.name),
            Tool("git.checkout", "Troca de branch/ref (rollback; descarta mudanças não commitadas).",
                 [ToolParam("ref", "string", "branch ou commit")],
                 self._checkout, self.name),
            Tool("git.commit", "Faz commit de todas as mudanças com uma mensagem.",
                 [ToolParam("message", "string", "mensagem do commit")],
                 self._commit, self.name),
        ]

    # -------------------- leitura (SAFE) -------------------- #
    async def _status(self, args: dict) -> ToolResult:
        await self.authorize("git.status.get", args)
        p = await _git_async("status", "--short", "--branch")
        if p.returncode != 0:
            return ToolResult.error((p.stderr or p.stdout).strip() or "git status falhou")
        return ToolResult.success(p.stdout.strip() or "(árvore limpa)")

    async def _diff(self, args: dict) -> ToolResult:
        await self.authorize("git.diff.get", args)
        extra = [args["path"]] if args.get("path") else []
        p = await _git_async("diff", "--", *extra) if extra else await _git_async("diff")
        if p.returncode != 0:
            return ToolResult.error((p.stderr or p.stdout).strip() or "git diff falhou")
        out = p.stdout.strip()
        return ToolResult.success(out[:6000] or "(sem mudanças)")

    async def _log(self, args: dict) -> ToolResult:
        await self.authorize("git.log.get", args)
        n = str(max(1, min(100, int(args.get("n", 10)))))
        p = await _git_async("log", f"-{n}", "--oneline")
        if p.returncode != 0:
            return ToolResult.error((p.stderr or p.stdout).strip() or "git log falhou")
        return ToolResult.success(p.stdout.strip() or "(sem commits)")

    async def _current(self, args: dict) -> ToolResult:
        await self.authorize("git.branch.get", args)
        p = await _git_async("rev-parse", "--abbrev-ref", "HEAD")
        if p.returncode != 0:
            return ToolResult.error((p.stderr or p.stdout).strip() or "git rev-parse falhou")
        return ToolResult.success(p.stdout.strip() or "(desconhecida)")

    # -------------------- escrita (gated) -------------------- #
    async def _branch_create(self, args: dict) -> ToolResult:
        await self.authorize("git.branch.create", args)
        name = str(args["name"]).strip()
        p = await _git_async("checkout", "-b", name)
        if p.returncode != 0:
            return ToolResult.error(f"falha ao criar branch: {(p.stderr or p.stdout).strip()}")
        return ToolResult.success(f"Branch '{name}' criada e ativa.")

    async def _checkout(self, args: dict) -> ToolResult:
        await self.authorize("git.checkout", args)
        ref = str(args["ref"]).strip()
        p = await _git_async("checkout", ref)
        if p.returncode != 0:
            return ToolResult.error(f"falha no checkout: {(p.stderr or p.stdout).strip()}")
        return ToolResult.success(f"Agora em '{ref}'.")

    async def _commit(self, args: dict) -> ToolResult:
        await self.authorize("git.commit", args)
        staged = await _git_async("add", "-A")
        if staged.returncode != 0:
            out = (staged.stderr or staged.stdout).strip()
            return ToolResult.error(f"falha ao preparar o commit: {out}")
        p = await _git_async("commit", "-m", str(args["message"]))
        out = (p.stdout or p.stderr).strip()
        if p.returncode != 0:
            return ToolResult.error(f"falha no commit: {out}")
        return ToolResult.success(out[:400])
