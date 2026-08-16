"""Document Agent — lê e cria documentos (PDF, Word, Excel, PowerPoint, texto).

Bundle de tools (não é orquestrador) para o mesmo tool-loop. Confinado ao
sandbox e sob ``authorize()`` como qualquer agente. Formatos de texto (txt/md/
csv/json…) funcionam SEM dependência; PDF/DOCX/XLSX/PPTX usam libs OPCIONAIS
(``pip install -e ".[docs]"``) — sem elas, degrada com uma mensagem clara em vez
de quebrar. Tudo LOCAL/offline. O texto extraído é tratado como DADO externo
(anti prompt-injection) ao voltar pro modelo.
"""

from __future__ import annotations

import csv
import importlib
import io
from pathlib import Path

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("document_agent")

MAX_CHARS = 200_000
_INSTALL_HINT = 'este formato requer libs opcionais — instale: pip install -e ".[docs]"'

# formatos de texto puro (stdlib, sem dependência)
_TEXT_EXT = {
    ".txt", ".md", ".markdown", ".rst", ".json", ".log", ".xml", ".html",
    ".htm", ".ini", ".cfg", ".yaml", ".yml", ".toml", ".tsv",
}


def _need(module: str):
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise RuntimeError(_INSTALL_HINT) from exc


def _extract_pdf(path: Path) -> str:
    pypdf = _need("pypdf")
    reader = pypdf.PdfReader(str(path))
    return "\n\n".join((pg.extract_text() or "") for pg in reader.pages)


def _extract_docx(path: Path) -> str:
    docx = _need("docx")
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_xlsx(path: Path) -> str:
    openpyxl = _need("openpyxl")
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    out: list[str] = []
    for ws in wb.worksheets:
        out.append(f"# planilha: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            if any(cells):
                out.append("\t".join(cells))
    return "\n".join(out)


def _extract_pptx(path: Path) -> str:
    pptx = _need("pptx")
    prs = pptx.Presentation(str(path))
    out: list[str] = []
    for i, slide in enumerate(prs.slides, 1):
        out.append(f"# slide {i}")
        for shape in slide.shapes:
            if shape.has_text_frame:
                out.append(shape.text_frame.text)
    return "\n".join(out)


def _extract_csv(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        rows = list(csv.reader(fh))
    return "\n".join("\t".join(r) for r in rows)


_EXTRACTORS = {".pdf": _extract_pdf, ".docx": _extract_docx, ".xlsx": _extract_xlsx,
               ".pptx": _extract_pptx, ".csv": _extract_csv}


class DocumentAgent(BaseAgent):
    name = "documents"
    description = (
        "Lê e cria documentos: PDF, Word (docx), Excel (xlsx), PowerPoint (pptx), "
        "CSV, TXT e Markdown. Use docs.read para analisar um arquivo anexado."
    )

    def __init__(self, deps: AgentDeps) -> None:
        super().__init__(deps)
        self.sandbox = deps.sandbox

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="docs.read",
                description=(
                    "Extrai o TEXTO de um documento (pdf, docx, xlsx, pptx, csv, txt, "
                    "md) para análise/resumo. Caminho relativo ao workspace."
                ),
                params=[ToolParam("path", "string", "ex.: contrato.pdf")],
                handler=self._read,
                agent=self.name,
            ),
            Tool(
                name="docs.create",
                description=(
                    "Cria um documento a partir de texto/markdown. Formato pelo "
                    "sufixo do caminho: .pdf, .docx, .md ou .txt. Pede confirmação."
                ),
                params=[
                    ToolParam("path", "string", "destino, ex.: relatorio.pdf"),
                    ToolParam("content", "string", "conteúdo (texto ou markdown)"),
                    ToolParam("title", "string", "título opcional", required=False),
                ],
                handler=self._create,
                agent=self.name,
            ),
        ]

    # ------------------------------ leitura ---------------------------- #
    async def _read(self, args: dict) -> ToolResult:
        await self.authorize("docs.read", args)          # leitura → SAFE
        path = self.sandbox.resolve(args["path"])
        if not path.is_file():
            return ToolResult.error(f"Arquivo não encontrado: {args['path']}")
        ext = path.suffix.lower()
        try:
            if ext in _TEXT_EXT:
                text = path.read_text(encoding="utf-8", errors="replace")
            elif ext in _EXTRACTORS:
                text = _EXTRACTORS[ext](path)
            else:
                return ToolResult.error(
                    f"Formato '{ext or '?'}' não suportado para texto. "
                    "Para binários use o Binary Agent; imagens, o Vision Agent."
                )
        except RuntimeError as exc:                      # lib opcional ausente
            return ToolResult.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Falha ao ler '{args['path']}': {exc}")
        text = (text or "").strip()
        clipped = text[:MAX_CHARS]
        return ToolResult.success(
            clipped or "(documento sem texto extraível)",
            path=str(path), chars=len(text), truncated=len(text) > MAX_CHARS,
        )

    # ------------------------------ criação ---------------------------- #
    async def _create(self, args: dict) -> ToolResult:
        await self.authorize("docs.create", args)        # escrita → REVIEW/L2
        path = self.sandbox.resolve(args["path"])
        content = args.get("content") or ""
        title = args.get("title") or ""
        ext = path.suffix.lower()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if ext in (".txt", ".md", ".markdown"):
                body = f"# {title}\n\n{content}" if title and ext != ".txt" else content
                path.write_text(body, encoding="utf-8")
            elif ext == ".docx":
                self._create_docx(path, title, content)
            elif ext == ".pdf":
                self._create_pdf(path, title, content)
            else:
                return ToolResult.error(
                    f"Não sei criar '{ext or '?'}'. Use .pdf, .docx, .md ou .txt."
                )
        except RuntimeError as exc:
            return ToolResult.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            return ToolResult.error(f"Falha ao criar '{args['path']}': {exc}")
        size = path.stat().st_size
        return ToolResult.success(
            f"Documento criado: {args['path']} ({size} bytes).", path=str(path), bytes=size)

    @staticmethod
    def _create_docx(path: Path, title: str, content: str) -> None:
        docx = _need("docx")
        doc = docx.Document()
        if title:
            doc.add_heading(title, level=0)
        for line in content.split("\n"):
            s = line.rstrip()
            if s.startswith("## "):
                doc.add_heading(s[3:], level=2)
            elif s.startswith("# "):
                doc.add_heading(s[2:], level=1)
            elif s.startswith(("- ", "* ")):
                doc.add_paragraph(s[2:], style="List Bullet")
            else:
                doc.add_paragraph(s)
        doc.save(str(path))

    @staticmethod
    def _create_pdf(path: Path, title: str, content: str) -> None:
        fpdf = _need("fpdf")                             # fpdf2 expõe o módulo 'fpdf'
        from fpdf.enums import XPos, YPos

        pdf = fpdf.FPDF()
        pdf.add_page()

        def _emit(text: str, size: int) -> None:
            pdf.set_font("Helvetica", size=size)
            # fontes core do fpdf2 são latin-1; preserva acentos PT, troca exóticos
            safe = text.encode("latin-1", "replace").decode("latin-1")
            # new_x=LMARGIN/new_y=NEXT: volta à margem esquerda e desce uma linha
            pdf.multi_cell(0, size * 0.6, safe, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if title:
            _emit(title, 16)
            pdf.ln(4)
        for line in content.split("\n"):
            _emit(line if line.strip() else " ", 12)
        pdf.output(str(path))
