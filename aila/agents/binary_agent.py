"""Binary Agent — análise de arquivos binários e integração com Ghidra.

⚠️  FASE 3. Fornece triagem básica de binários (tipo, strings, cabeçalho) e
um ponto de integração para o Ghidra headless (análise/descompilação).

A integração completa com o Ghidra requer instalação externa e é acionada por
``ghidra_headless_path`` na configuração (fase futura).
"""

from __future__ import annotations

import string

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("binary_agent")

_MAGIC = {
    b"MZ": "Executável Windows (PE/DOS)",
    b"\x7fELF": "Executável ELF (Linux)",
    b"\x89PNG": "Imagem PNG",
    b"PK\x03\x04": "Arquivo ZIP/derivado (jar, docx, ...)",
    b"%PDF": "Documento PDF",
    b"\xca\xfe\xba\xbe": "Java class / Mach-O fat",
}


class BinaryAgent(BaseAgent):
    name = "binary"
    description = (
        "Faz triagem de arquivos binários (tipo, strings, cabeçalho) e prepara "
        "a integração com o Ghidra para descompilação."
    )

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="binary.identify",
                description="Identifica o tipo de um arquivo binário pelo cabeçalho.",
                params=[ToolParam("path", "string", "Caminho no workspace")],
                handler=self._identify,
                agent=self.name,
            ),
            Tool(
                name="binary.strings",
                description="Extrai strings ASCII legíveis de um binário.",
                params=[
                    ToolParam("path", "string", "Caminho no workspace"),
                    ToolParam("min_len", "integer", "Tamanho mínimo", required=False),
                ],
                handler=self._strings,
                agent=self.name,
            ),
        ]

    async def _identify(self, args: dict) -> ToolResult:
        await self.authorize("binary.identify", args)
        path = self.deps.sandbox.resolve(args["path"])
        if not path.is_file():
            return ToolResult.error(f"Arquivo não encontrado: {args['path']}")
        head = path.read_bytes()[:16]
        kind = next((v for k, v in _MAGIC.items() if head.startswith(k)), "Desconhecido")
        return ToolResult.success(
            f"Tipo: {kind}\nHex inicial: {head.hex(' ')}\nTamanho: {path.stat().st_size} bytes"
        )

    async def _strings(self, args: dict) -> ToolResult:
        await self.authorize("binary.strings", args)
        path = self.deps.sandbox.resolve(args["path"])
        if not path.is_file():
            return ToolResult.error(f"Arquivo não encontrado: {args['path']}")
        min_len = int(args.get("min_len", 4))
        data = path.read_bytes()[:2_000_000]
        printable = set(bytes(string.printable[:-5], "ascii"))
        out: list[str] = []
        cur = bytearray()
        for b in data:
            if b in printable:
                cur.append(b)
            else:
                if len(cur) >= min_len:
                    out.append(cur.decode("ascii", "ignore"))
                cur.clear()
        if len(cur) >= min_len:
            out.append(cur.decode("ascii", "ignore"))
        preview = "\n".join(out[:200])
        return ToolResult.success(preview or "(nenhuma string encontrada)", total=len(out))
