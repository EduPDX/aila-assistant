"""Memory Agent — memória de longo prazo explícita.

Além da recuperação automática (feita pela engine a cada turno), este agente dá
à IA controle explícito sobre a memória: salvar um fato importante para lembrar
depois, ou buscar o que já sabe sobre um assunto.
"""

from __future__ import annotations

from aila.agents.base import BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("memory_agent")


class MemoryAgent(BaseAgent):
    name = "memory"
    description = (
        "Memória de longo prazo: salvar fatos importantes para lembrar em "
        "conversas futuras e buscar o que já foi aprendido."
    )

    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="memory.save",
                description="Salva um fato/preferência importante na memória de longo prazo.",
                params=[
                    ToolParam("text", "string", "O fato a lembrar (conciso e completo)")
                ],
                handler=self._save,
                agent=self.name,
            ),
            Tool(
                name="memory.search",
                description="Busca na memória de longo prazo por um assunto.",
                params=[
                    ToolParam("query", "string", "Assunto/pergunta"),
                    ToolParam("top_k", "integer", "Quantos resultados", required=False),
                ],
                handler=self._search,
                agent=self.name,
            ),
        ]

    def _store(self):
        return self.deps.memory

    async def _save(self, args: dict) -> ToolResult:
        # A memória é estado interno da IA (não é o sistema do usuário), então
        # não é bloqueada pelo modo somente-leitura — apenas auditada.
        if self._store() is None:
            return ToolResult.error("Memória de longo prazo desabilitada.")
        mid = await self._store().add(args["text"], kind="fact")
        self.deps.permissions.audit.record(
            "memory.save", self.name, args, f"saved:#{mid}", allowed=True
        )
        return ToolResult.success(f"Memória salva (#{mid}).", id=mid)

    async def _search(self, args: dict) -> ToolResult:
        await self.authorize("memory.search", args)
        if self._store() is None:
            return ToolResult.error("Memória de longo prazo desabilitada.")
        hits = await self._store().search(args["query"], top_k=int(args.get("top_k", 4)))
        if not hits:
            return ToolResult.success("Nada relevante na memória.")
        lines = [f"[{h.score:.2f}] {h.text}" for h in hits]
        return ToolResult.success("\n".join(lines), count=len(hits))
