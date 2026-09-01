"""Binary Agent — análise de arquivos binários e integração com Ghidra.

FASE 3. Triagem que roda **sem dependências externas** (tipo, strings, entropia,
cabeçalho PE) e uma ponte para o **Ghidra headless** (descompilação), habilitada
quando ``binary.ghidra_path`` aponta para uma instalação do Ghidra.

Todas as operações são **leitura** (funcionam em modo somente-leitura).
"""

from __future__ import annotations

import asyncio
import math
import string
import struct
import subprocess
import tempfile
from pathlib import Path

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("binary_agent")

_GHIDRA_SCRIPT_DIR = Path(__file__).resolve().parent.parent / "tools" / "ghidra"

_MAGIC = {
    b"MZ": "Executável Windows (PE/DOS)",
    b"\x7fELF": "Executável ELF (Linux)",
    b"\x89PNG": "Imagem PNG",
    b"PK\x03\x04": "Arquivo ZIP/derivado (jar, docx, apk, ...)",
    b"%PDF": "Documento PDF",
    b"\xca\xfe\xba\xbe": "Java class / Mach-O fat",
    b"\xcf\xfa\xed\xfe": "Mach-O 64-bit (macOS)",
    b"\x1f\x8b": "Gzip",
    b"Rar!": "Arquivo RAR",
    b"\x00asm": "WebAssembly",
}

# Máquinas PE comuns (IMAGE_FILE_MACHINE_*)
_PE_MACHINE = {0x14C: "x86 (32-bit)", 0x8664: "x64 (AMD64)", 0xAA64: "ARM64", 0x1C0: "ARM"}


class BinaryAgent(BaseAgent):
    name = "binary"
    description = (
        "Analisa arquivos binários: identifica o tipo, extrai strings, mede "
        "entropia (detecta packed/encrypted), lê o cabeçalho PE e descompila "
        "com o Ghidra (se configurado)."
    )

    def __init__(self, deps: AgentDeps) -> None:
        super().__init__(deps)
        self.ghidra_path = deps.settings.binary.ghidra_path
        self.timeout = deps.settings.binary.analysis_timeout

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="binary.identify",
                description="Identifica o tipo de um arquivo pelo cabeçalho (magic bytes).",
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
            Tool(
                name="binary.entropy",
                description="Mede a entropia de Shannon (alta ~>7.5 sugere packed/cifrado).",
                params=[ToolParam("path", "string", "Caminho no workspace")],
                handler=self._entropy,
                agent=self.name,
            ),
            Tool(
                name="binary.pe_info",
                description="Lê o cabeçalho PE de um executável Windows (seções, arquitetura).",
                params=[ToolParam("path", "string", "Caminho no workspace")],
                handler=self._pe_info,
                agent=self.name,
            ),
            Tool(
                name="binary.decompile",
                description="Descompila um binário com o Ghidra headless (requer Ghidra).",
                params=[
                    ToolParam("path", "string", "Caminho no workspace"),
                    ToolParam("function", "string", "Função-alvo (opcional)", required=False),
                ],
                handler=self._decompile,
                agent=self.name,
            ),
        ]

    # ------------------------------------------------------------------ #
    def _resolve_file(self, rel: str) -> tuple[Path | None, str | None]:
        path = self.deps.sandbox.resolve(rel, read=True)
        if not path.is_file():
            return None, f"Arquivo não encontrado: {rel}"
        return path, None

    async def _identify(self, args: dict) -> ToolResult:
        await self.authorize("binary.identify.get", args)  # leitura
        path, err = self._resolve_file(args["path"])
        if err:
            return ToolResult.error(err)
        head = path.read_bytes()[:16]
        kind = next((v for k, v in _MAGIC.items() if head.startswith(k)), "Desconhecido")
        size = path.stat().st_size
        return ToolResult.success(
            f"Tipo: {kind}\nTamanho: {size:,} bytes\nHex inicial: {head.hex(' ')}",
            kind=kind,
            size=size,
        )

    async def _strings(self, args: dict) -> ToolResult:
        await self.authorize("binary.strings.get", args)  # leitura
        path, err = self._resolve_file(args["path"])
        if err:
            return ToolResult.error(err)
        try:
            min_len = max(1, min(256, int(args.get("min_len", 4))))
        except (TypeError, ValueError):
            return ToolResult.error("min_len deve ser um número inteiro entre 1 e 256.")
        data = path.read_bytes()[:5_000_000]
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
        preview = "\n".join(out[:300])
        return ToolResult.success(preview or "(nenhuma string encontrada)", total=len(out))

    async def _entropy(self, args: dict) -> ToolResult:
        await self.authorize("binary.entropy.get", args)  # leitura
        path, err = self._resolve_file(args["path"])
        if err:
            return ToolResult.error(err)
        data = path.read_bytes()[:4_000_000]
        if not data:
            return ToolResult.error("Arquivo vazio.")
        counts = [0] * 256
        for b in data:
            counts[b] += 1
        n = len(data)
        entropy = -sum((c / n) * math.log2(c / n) for c in counts if c)
        if entropy > 7.5:
            verdict = "MUITO ALTA — provavelmente comprimido/cifrado/packed"
        elif entropy > 6.5:
            verdict = "alta — possível compressão"
        else:
            verdict = "normal para código/dados"
        return ToolResult.success(
            f"Entropia de Shannon: {entropy:.3f} / 8.0\nAvaliação: {verdict}",
            entropy=round(entropy, 3),
        )

    async def _pe_info(self, args: dict) -> ToolResult:
        await self.authorize("binary.pe.info", args)  # leitura
        path, err = self._resolve_file(args["path"])
        if err:
            return ToolResult.error(err)
        data = path.read_bytes()
        if data[:2] != b"MZ":
            return ToolResult.error("Não é um executável Windows (falta assinatura MZ).")
        try:
            e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
            if data[e_lfanew : e_lfanew + 4] != b"PE\x00\x00":
                return ToolResult.error("Assinatura PE não encontrada.")
            coff = e_lfanew + 4
            machine, n_sections, _timestamp = struct.unpack_from("<HHI", data, coff)
            opt_size = struct.unpack_from("<H", data, coff + 16)[0]
            magic = struct.unpack_from("<H", data, coff + 20)[0]
            bits = {0x10B: "PE32", 0x20B: "PE32+ (64-bit)"}.get(magic, f"0x{magic:x}")
            arch = _PE_MACHINE.get(machine, f"0x{machine:x}")
            sec_off = coff + 20 + opt_size
            sections = []
            for i in range(n_sections):
                base = sec_off + i * 40
                if base + 40 > len(data):
                    break
                name = data[base : base + 8].split(b"\x00")[0].decode("ascii", "ignore")
                vsize, vaddr, rawsize = struct.unpack_from("<III", data, base + 8)
                sections.append(f"  {name:<8} vaddr=0x{vaddr:x} size={rawsize}")
        except (struct.error, IndexError) as exc:
            return ToolResult.error(f"Cabeçalho PE malformado: {exc}")
        report = (
            f"Formato: {bits}\nArquitetura: {arch}\nSeções ({n_sections}):\n"
            + "\n".join(sections)
        )
        return ToolResult.success(report, arch=arch, sections=n_sections)

    async def _decompile(self, args: dict) -> ToolResult:
        await self.authorize("binary.decompile.get", args)  # leitura (só analisa)
        if not self.ghidra_path:
            return ToolResult.error(
                "Ghidra não configurado. Instale o Ghidra e defina 'binary.ghidra_path' "
                "(a pasta que contém support/analyzeHeadless). Veja docs/BINARY.md."
            )
        path, err = self._resolve_file(args["path"])
        if err:
            return ToolResult.error(err)

        headless = self._find_headless()
        if headless is None:
            return ToolResult.error(
                f"analyzeHeadless não encontrado em '{self.ghidra_path}/support'. "
                f"Confira 'binary.ghidra_path'."
            )

        with tempfile.TemporaryDirectory() as proj:
            cmd = [
                str(headless), proj, "aila_tmp",
                "-import", str(path),
                "-scriptPath", str(_GHIDRA_SCRIPT_DIR),
                "-postScript", "decompile_headless.py",
            ]
            if args.get("function"):
                cmd.append(str(args["function"]))
            cmd.append("-deleteProject")
            try:
                proc = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired:
                return ToolResult.error(
                    f"Ghidra excedeu o tempo limite ({self.timeout}s). "
                    f"Aumente 'binary.analysis_timeout' para binários grandes."
                )
            except OSError as exc:
                return ToolResult.error(f"Falha ao iniciar o Ghidra: {exc}")

        out = proc.stdout or ""
        begin, end = out.find("AILA_GHIDRA_BEGIN"), out.find("AILA_GHIDRA_END")
        if proc.returncode != 0 or begin == -1 or end <= begin:
            tail = (proc.stderr or out)[-800:]
            return ToolResult.error(f"Ghidra não produziu saída esperada.\n{tail}")
        result = out[begin + len("AILA_GHIDRA_BEGIN") : end].strip()
        return ToolResult.success(result[:8000])

    def _find_headless(self) -> Path | None:
        base = Path(self.ghidra_path) / "support"
        for name in ("analyzeHeadless.bat", "analyzeHeadless"):
            cand = base / name
            if cand.exists():
                return cand
        return None
