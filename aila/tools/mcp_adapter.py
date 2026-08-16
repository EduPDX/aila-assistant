"""Adaptador MCP (Model Context Protocol) — Fase 7b.

Conecta servidores MCP EXTERNOS via stdio e expõe as ferramentas deles como
tools nativas da Aila. Cliente MÍNIMO de JSON-RPC 2.0 (newline-delimited) escrito
só com a stdlib (asyncio.subprocess) — ZERO dependência nova.

Princípios (inegociáveis):
    - OPT-IN / OFFLINE-SAFE: ``mcp.enabled=false`` por padrão → nada conecta,
      comportamento atual intacto. Falha ao conectar NÃO derruba o app.
    - TUDO passa por ``authorize()``: cada tool externa vira ``mcp.<srv>.<tool>``
      e é REVIEW/L2 por padrão (não são leituras) — o usuário controla via
      ``security.action_levels`` / autonomia. Nada contorna a segurança.

Não é uma implementação completa do MCP (sem SSE/HTTP, sem resources/prompts):
só o essencial — initialize, tools/list, tools/call — que cobre o uso como
provedor de ferramentas.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import TYPE_CHECKING, Any

from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

if TYPE_CHECKING:
    from aila.core.config import MCPConfig
    from aila.security.permissions import PermissionManager
    from aila.tools.registry import ToolRegistry

log = get_logger("mcp")

_PROTOCOL_VERSION = "2024-11-05"


class MCPError(Exception):
    """Erro JSON-RPC devolvido pelo servidor MCP."""


class MCPClient:
    """Cliente stdio de um servidor MCP (um processo)."""

    def __init__(self, name: str, command: str, args: list[str] | None = None,
                 env: dict[str, str] | None = None) -> None:
        self.name = name
        self.command = command
        self.args = list(args or [])
        self.env = dict(env or {})
        self._proc: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._id = 0

    # ----------------------------- ciclo de vida ---------------------- #
    async def start(self, timeout: float = 20.0) -> dict:
        env = {**os.environ, **self.env}
        self._proc = await asyncio.create_subprocess_exec(
            self.command, *self.args,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=env,
        )
        self._reader = asyncio.create_task(self._read_loop())
        init = await self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "aila", "version": "0.1.0"},
        }, timeout=timeout)
        await self._notify("notifications/initialized", {})
        return init or {}

    async def close(self) -> None:
        if self._reader is not None:
            self._reader.cancel()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()
        if self._proc is not None:
            try:
                self._proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except (TimeoutError, ProcessLookupError):
                pass

    # ------------------------------ operações ------------------------- #
    async def list_tools(self) -> list[dict]:
        res = await self._request("tools/list", {})
        return list((res or {}).get("tools", []))

    async def call_tool(self, name: str, arguments: dict, timeout: float = 60.0) -> tuple[str, bool]:
        """Retorna (texto, is_error). Junta os blocos de conteúdo do tipo text."""
        res = await self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}, timeout=timeout)
        res = res or {}
        blocks = res.get("content", []) or []
        text = "\n".join(b.get("text", "") for b in blocks
                         if isinstance(b, dict) and b.get("type") == "text")
        return text, bool(res.get("isError"))

    # ------------------------------- interno -------------------------- #
    async def _read_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            while True:
                line = await self._proc.stdout.readline()
                if not line:                        # EOF: processo encerrou
                    break
                raw = line.strip()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue                        # servidor pode logar em stdout
                mid = msg.get("id")
                fut = self._pending.pop(mid, None) if mid is not None else None
                if fut is not None and not fut.done():
                    if "error" in msg:
                        fut.set_exception(MCPError(str(msg["error"])))
                    else:
                        fut.set_result(msg.get("result"))
        except asyncio.CancelledError:
            pass

    async def _send(self, msg: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

    async def _request(self, method: str, params: dict, timeout: float = 30.0) -> Any:
        self._id += 1
        mid = self._id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        await self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(mid, None)

    async def _notify(self, method: str, params: dict) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})


class MCPManager:
    """Guarda os clientes conectados p/ encerrar no shutdown."""

    def __init__(self) -> None:
        self.clients: list[MCPClient] = []

    async def close_all(self) -> None:
        for c in self.clients:
            try:
                await c.close()
            except Exception as exc:  # noqa: BLE001
                log.warning(f"falha ao fechar MCP '{c.name}': {exc!r}")


def _params_from_schema(schema: dict | None) -> list[ToolParam]:
    props = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])
    out: list[ToolParam] = []
    for pname, ps in props.items():
        ps = ps or {}
        typ = ps.get("type", "string")
        if isinstance(typ, list):                   # ex.: ["string","null"]
            typ = next((t for t in typ if t != "null"), "string")
        desc = ps.get("description") or ps.get("title") or ""
        out.append(ToolParam(pname, typ, desc, required=pname in required))
    return out


def _make_handler(client: MCPClient, orig: str, action: str,
                  permissions: PermissionManager, call_timeout: float):
    async def handler(args: dict) -> ToolResult:
        await permissions.check(action, "mcp", args)   # nada contorna authorize()
        try:
            text, is_error = await client.call_tool(orig, args, timeout=call_timeout)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"MCP {orig} falhou: {exc}")
        if is_error:
            return ToolResult.error(text or f"{orig} retornou erro.")
        return ToolResult.success(text or "(sem saída)")
    return handler


async def connect_and_register(
    cfg: MCPConfig, registry: ToolRegistry, permissions: PermissionManager,
) -> MCPManager:
    """Conecta os servidores habilitados e registra as tools no registry.
    Best-effort: um servidor indisponível é logado e ignorado (não derruba nada)."""
    manager = MCPManager()
    if not getattr(cfg, "enabled", False):
        return manager
    for srv in cfg.servers:
        if not getattr(srv, "enabled", True) or not srv.command:
            continue
        client = MCPClient(srv.name, srv.command, srv.args, srv.env)
        try:
            await client.start(timeout=cfg.startup_timeout)
            tools = await client.list_tools()
        except Exception as exc:  # noqa: BLE001
            log.warning(f"MCP '{srv.name}' indisponível: {exc!r}")
            await client.close()
            continue
        manager.clients.append(client)
        count = 0
        for t in tools:
            orig = t.get("name")
            if not orig:
                continue
            tname = f"mcp.{srv.name}.{orig}"
            desc = f"[MCP {srv.name}] {t.get('description', '')}".strip()
            tool = Tool(
                name=tname, description=desc,
                params=_params_from_schema(t.get("inputSchema")),
                handler=_make_handler(client, orig, tname, permissions, cfg.call_timeout),
                agent="mcp",
            )
            try:
                registry.register(tool)
                count += 1
            except ValueError:
                log.warning(f"tool MCP duplicada, ignorada: {tname}")
        log.info(f"MCP '{srv.name}': {count} ferramenta(s) registrada(s)")
    return manager
