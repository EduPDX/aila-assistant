"""Classificação de turno: decide o TIPO de tarefa (RouteTask) e se o turno
deve oferecer ferramentas, a partir do TEXTO do usuário. Funções puras, sem
estado — extraídas de engine.py (Fase 2) para o engine voltar a ser só
orquestrador. O engine re-exporta estes símbolos para compatibilidade (testes
e chamadas existentes importam de aila.core.engine)."""
from __future__ import annotations

import re
from pathlib import Path

from aila.llm.router import RouteTask

_CASUAL_RX = re.compile(
    r"^(oi+|ol[áa]+|e a[íi]|eae|opa|al[ôo]|hey|hi|hello|bom dia|boa tarde|boa noite|"
    r"tudo (bem|certo|jo[ií]a|tranquilo|ok)|como (vai|voc[êe] (est[áa]|ta)|est[áa]|ta)|"
    r"obrigad[oa]|obg|valeu|vlw|beleza|blz|de nada|tchau|at[ée] (mais|logo|breve)|"
    r"boa|legal|massa|show|top|kk+|k?haha\w*|rs+)\b", re.IGNORECASE)
_CODE_RX = re.compile(
    r"(```|\b(c[óo]digo|program\w+|fun[çc][ãa]o|function|def |class |m[ée]todo|"
    r"bug|erro|exce[çc][ãa]o|traceback|compil\w+|refator\w+|implement\w+|corrig\w+|"
    r"depur\w+|debug|script|api\b|endpoint|reposit[óo]rio|commit|git\b|lint|"
    r"testes?\b|pytest|npm\b|cargo\b|\.py\b|\.js\b|\.ts\b|\.go\b|\.rs\b))",
    re.IGNORECASE)


_CODE_ACTION_RX = re.compile(
    r"\b(salv\w*|salve|crie|criar|gere|gera|rod\w*|execut\w*|edit\w*|corrij\w*|"
    r"conserta|arruma|testa|teste[s]?\b|na pasta|no arquivo|no diret[óo]rio|"
    r"documentos?|desktop|downloads?)\b", re.IGNORECASE)


def normalize_user_write_call(name: str, args: dict, user_text: str) -> tuple[str, dict]:
    """Roteia escrita destinada a uma pasta pessoal para ``file.write``.

    Modelos pequenos confundem ``code.write_file`` (autoedição/L5) com
    ``file.write`` (arquivo do usuário/L2) e costumam enviar só o nome relativo.
    A intenção explícita define o destino, sem ampliar as raízes do sandbox.
    """
    if name not in {"file.write", "code.write_file"} or not isinstance(args, dict):
        return name, args
    text = user_text or ""
    low = text.casefold()
    folder_kind = (
        "desktop" if ("desktop" in low or "área de trabalho" in low or "area de trabalho" in low)
        else "downloads" if "download" in low
        else "documents" if ("documento" in low or "documents" in low) else None
    )
    if folder_kind is None:
        return name, args
    raw_path = str(args.get("path") or "").strip()
    filename = Path(raw_path.replace("\\", "/")).name if raw_path else ""
    if not filename or "." not in filename:
        requested = re.search(r"\b([\w-]+\.[A-Za-z][A-Za-z0-9]{0,7})\b", text)
        filename = requested.group(1) if requested else ""
    if not filename and str(args.get("content") or ""):
        public_class = re.search(r"\bpublic\s+class\s+([A-Za-z_$][\w$]*)", args["content"])
        if public_class:
            filename = public_class.group(1) + ".java"
    if not filename:
        return name, args
    from aila.security.sandbox import user_folder

    routed = dict(args)
    routed["path"] = str(user_folder(folder_kind) / filename)
    return "file.write", routed


# Ordens ao avatar/corpo (gesto, pose, olhar) — curtas, mas são AÇÃO, não papo.
_AVATAR_CMD_RX = re.compile(
    r"\b(levant\w+|erga|abaix\w+|acen\w+|tchau|dance|dan[çc]\w+|sorri\w+|"
    r"aponte|apont\w+|olhe|olha p|vire|gire|balan[çc]\w+|bata palma|palmas|"
    r"pule|sente|senta|fique de p[ée]|gesto|pose|movimento|bra[çc]os?|m[ãa]os?|cabe[çc]a)\b",
    re.IGNORECASE)
# Verbos imperativos em geral (pedido de AÇÃO) — desqualifica "conversa casual"
_COMMAND_RX = re.compile(
    r"\b(fa[çc]a|faz|cri\w+|escrev\w+|salv\w+|apag\w+|delet\w+|mov\w+|copi\w+|"
    r"renome\w+|abr\w+|fech\w+|mostr\w+|list\w+|busc\w+|procur\w+|pesquis\w+|"
    r"rod\w+|execut\w+|test\w+|corrij\w+|conserta|arrum\w+|analis\w+|revis\w+|"
    r"me diga|diga|fale|conte|explique|calcule|traduza|resum\w+)\b",
    re.IGNORECASE)


def _is_avatar_command(t: str) -> bool:
    return bool(_AVATAR_CMD_RX.search(t or ""))


def _is_code_request(t: str) -> bool:
    return bool(_CODE_RX.search(t or ""))


def _is_casual(t: str) -> bool:
    """Cumprimento/conversa curta e sem sinais de tarefa → tratar como 'básico'
    (roteia p/ o modelo LOCAL, rápido, sem ferramentas)."""
    t = (t or "").strip()
    if not t:
        return False
    # uma ORDEM ("levante os braços", "acene") é ação, mesmo sendo curta:
    # tratá-la como papo tirava as ferramentas e a Aila dizia "não consigo".
    if _is_avatar_command(t) or _COMMAND_RX.search(t) or _is_code_request(t):
        return False
    # se depende do mundo real (hora, arquivo, web...), não é papo — mesmo curto
    if _needs_tools(t):
        return False
    words = t.split()
    if _CASUAL_RX.match(t) and len(words) <= 8:
        return True
    return len(words) <= 3


#: sinais de que a resposta depende de algo FORA do modelo (arquivo, web, anexo,
#: memória, PC). Sem nenhum deles, a pergunta é conhecimento puro — oferecer
#: ferramentas só faz o modelo pequeno tatear (docs.read, web.fetch…) e ATRASAR.
_PRECISA_FERRAMENTA_RX = re.compile(
    r"\bpesquis\w+|\bbusc\w+|\bprocur\w+|\bgoogl\w+|na (web|internet)|\barquivo|\bpasta|\bdiret[óo]rio|\bdocumento|\bplanilha|\banexo|\bimagem|\bprint\b|\btela\b|\blembr\w+|\bguard\w+|\bsalv\w+|\banot\w+|\bhoje\b|\bhoras?\b|\bque horas|\bdata\b|\bagora\b|\batual\w*|\b[úu]ltim\w+|\bnot[íi]cia\w*|https?://|[A-Za-z]:\\\\|\b\w+\.(py|js|ts|md|txt|json|csv|pdf|docx?|xlsx?)\b|\[Anexo|\[Pasta anexada",
    re.IGNORECASE)


def _needs_tools(t: str) -> bool:
    """A mensagem depende de algo externo (arquivo/web/anexo/memória/PC)?"""
    return bool(_PRECISA_FERRAMENTA_RX.search(t or ""))


def _classify_task(user_text: str, mode: str) -> tuple[RouteTask, bool]:
    """Classifica a mensagem → (RouteTask p/ o router, oferecer_ferramentas?).
    Faz o modelo certo ser escolhido de cara, evitando o 'bounce' favorito→local."""
    if mode == "chat":
        return RouteTask(kind="chat", needs_tools=False), False
    if _is_casual(user_text):
        # básico/casual → LOCAL (prefer_local filtra p/ só local), sem ferramentas
        return RouteTask(kind="basic", needs_tools=False, prefer_local=True), False
    if _is_avatar_command(user_text):
        # gesto/pose SEMPRE vence a detecção de código ("levante a mão p/ testes"
        # não é tarefa de código!). Vai p/ o LOCAL, rápido. Se o Decision Engine já
        # cuida do gesto, NÃO oferecemos ferramentas — senão o modelo chama
        # avatar.gesture várias vezes à toa. Gesto não mapeado ("olhe p/ a
        # esquerda") mantém ferramentas p/ o modelo tentar.
        from aila.mind.decision_engine import decide_gesture

        tem_gesto = decide_gesture(user_text) is not None
        return RouteTask(kind="chat", needs_tools=not tem_gesto, prefer_local=True), (not tem_gesto)
    if _is_code_request(user_text):
        # código → cadeia 'code' das rules (ex.: Gemini, melhor em código; local é
        # fallback). NÃO forçamos mais local: as travadas na nuvem vinham do parser
        # de tool-call, que rejeitava código multi-linha (corrigido com strict=False).
        return RouteTask(kind="code", needs_tools=True), True
    # COMPLEXIDADE (Fase H): trivial → modelo pequeno/rápido; raciocínio PESADO →
    # cadeia 'reasoning' (ex.: Nemotron), só quando realmente vale a espera.
    from aila.mind.task_analyzer import analyze

    info = analyze(user_text)
    comp = info["complexity"]
    kind = "reasoning" if comp >= 0.6 else "chat"
    if not _needs_tools(user_text):
        # conhecimento puro ("por onde começo a estudar IA?"): responde do que
        # sabe. Ferramentas aqui só geram tentativas inúteis que atrasam.
        return RouteTask(kind=kind, needs_tools=False, complexity=comp), False
    return RouteTask(kind=kind, needs_tools=True, complexity=comp), True


def _tool_status(tool_name: str) -> str:
    """Mapeia o nome da ferramenta para um estado global da Aila."""
    if tool_name.startswith("code."):
        return "CODING"
    if tool_name.startswith(("vision.", "binary.")):
        return "ANALYZING_IMAGE" if tool_name.startswith("vision.") else "TOOL_RUNNING"
    if tool_name.startswith("file."):
        return "READING_FILE"
    if tool_name.startswith("web.") or tool_name.startswith("memory.search"):
        return "SEARCHING"
    return "TOOL_RUNNING"
