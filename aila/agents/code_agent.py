"""Code Agent — geração, análise e correção de código.

Usa um modelo especializado em código (ex.: deepseek-coder) via o mesmo
backend de LLM. Ele não executa código por padrão (isso é uma ação destrutiva
que exigirá o Computer Agent + confirmação numa fase futura).
"""

from __future__ import annotations

from aila.agents.base import AgentDeps, BaseAgent
from aila.core.logging import get_logger
from aila.tools.schema import Tool, ToolParam, ToolResult

log = get_logger("code_agent")


class CodeAgent(BaseAgent):
    name = "code"
    description = (
        "Escreve, explica, revisa e corrige código usando um modelo "
        "especializado (deepseek-coder). Não executa código."
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
