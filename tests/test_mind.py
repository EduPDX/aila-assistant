"""Cognitive Core — Fase B: identidade, personalidade e AilaSelf.

Nesta fase o self model ainda NÃO participa do turno; os testes garantem a
fundação (dados corretos, 1ª pessoa, capacidades reais) sem tocar no fluxo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aila.mind import AilaSelf, AilaState, BodyState, Identity, PersonalityTraits, load_identity


def test_identidade_padrao_fala_em_primeira_pessoa():
    ident = Identity()
    bloco = ident.prompt_block()
    assert ident.name == "Aila" and ident.self_reference == "eu"
    assert "primeira pessoa" in bloco.lower()
    assert "Aila" in bloco


def test_identidade_carrega_do_yaml_do_projeto():
    """config/identity.yaml é a fonte persistente (não um prompt no código)."""
    ident, pers = load_identity()
    assert ident.name == "Aila"
    assert 0.0 <= pers.curiosity <= 1.0
    assert pers.summary()                      # resumo legível, não números


def test_identidade_invalida_nao_derruba(tmp_path: Path):
    (tmp_path / "identity.yaml").write_text("identity: {curiosity: nao_e_numero}\n:\n", encoding="utf-8")
    ident, pers = load_identity(tmp_path)       # YAML torto → cai nos padrões
    assert ident.name == "Aila" and isinstance(pers, PersonalityTraits)


def test_override_local_sobrescreve(tmp_path: Path):
    (tmp_path / "identity.yaml").write_text(
        "identity:\n  name: Aila\n  role: base\npersonality:\n  formality: 0.9\n", encoding="utf-8")
    (tmp_path / "identity.local.yaml").write_text(
        "identity:\n  role: assistente do Eduardo\n", encoding="utf-8")
    ident, pers = load_identity(tmp_path)
    assert ident.role == "assistente do Eduardo"    # local venceu
    assert pers.formality == 0.9                    # base preservada


def test_personalidade_limita_valores():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PersonalityTraits(curiosity=1.7)            # fora de 0..1


def test_corpo_descreve_em_primeira_pessoa():
    """CASO OBRIGATÓRIO (item 31): mão levantada -> 'estou com a mão...',
    NUNCA 'o avatar está com a mão levantada'."""
    corpo = BodyState(hands={"left": "rest", "right": "raised"})
    d = corpo.describe()
    assert "estou" in d and "direita" in d
    assert "avatar" not in d.lower() and "o modelo" not in d.lower()

    olhando = BodyState(gaze_target="painel de análise")
    assert olhando.describe().startswith("estou olhando")

    assert BodyState().describe() == ""              # corpo neutro não polui o prompt


def test_self_agrega_e_gera_estado():
    eu = AilaSelf.load()
    eu.update_body(hands={"left": "rest", "right": "raised"}, gaze_target="grafico_02")
    eu.update_experience(activity="analyzing", emotion="focused")

    st = eu.state()
    assert isinstance(st, AilaState)
    assert st.identity.name == "Aila"
    assert st.emotion == "focused" and st.experience.activity == "analyzing"
    assert st.body.hands["right"] == "raised"
    assert eu.body.updated_at > 0                     # frescor registrado
    # o contrato com o frontend NÃO expõe qual LLM respondeu
    payload = st.to_event_payload()
    blob = str(payload).lower()
    assert "gemini" not in blob and "ollama" not in blob and "nemotron" not in blob


def test_prompt_block_e_curto_e_em_primeira_pessoa():
    eu = AilaSelf.load()
    eu.update_body(hands={"left": "rest", "right": "raised"})
    bloco = eu.prompt_block()
    assert "mão direita levantada" in bloco or "direita" in bloco
    assert "meu braço" in bloco or "minha mão" in bloco   # instrução de 1ª pessoa
    assert len(bloco) < 700                                # cabe em num_ctx pequeno


def test_capacidades_vem_das_ferramentas_reais():
    class _T:
        def __init__(self, n): self.name = n

    class _Reg:
        def all(self): return [_T("web.search"), _T("file.write"), _T("avatar.gesture")]

    eu = AilaSelf.load()
    eu.bind_capabilities(_Reg())
    assert eu.capabilities.can("pesquisa_web") and eu.capabilities.can("arquivos")
    assert eu.capabilities.can("controle_do_corpo")
    assert not eu.capabilities.can("visao")            # não registrada -> não promete
    eu.bind_capabilities(None)                          # registry ausente não quebra
    assert eu.capabilities.items == {}


# ------------------------------------------------------- Fase C: personalidade #

def test_estilo_muda_com_os_tracos():
    """Traços diferentes → estilo diferente. É isto que faz a personalidade
    aparecer no comportamento em vez de virar assunto."""
    from aila.mind import derive_style

    informal = derive_style(PersonalityTraits(formality=0.2, verbosity=0.2, playfulness=0.8))
    formal = derive_style(PersonalityTraits(formality=0.9, verbosity=0.9, playfulness=0.1))

    assert informal.tone == "informal" and informal.length == "curta" and informal.humor
    assert formal.tone == "formal" and formal.length == "explicativa" and not formal.humor
    assert informal.directives and formal.directives
    # a personalidade NUNCA manda falar sobre si mesma
    for d in informal.directives + formal.directives:
        assert "personalidade" not in d.lower()


def test_estilo_pergunta_quando_vago():
    from aila.mind import derive_style

    curiosa = derive_style(PersonalityTraits(curiosity=0.9, patience=0.9))
    seca = derive_style(PersonalityTraits(curiosity=0.2, patience=0.2))
    assert curiosa.ask_when_vague and not seca.ask_when_vague
    assert any("pergunta" in d.lower() for d in curiosa.directives)


def test_confianca_controla_hedge():
    from aila.mind import derive_style

    assert derive_style(PersonalityTraits(confidence=0.3)).hedge
    assert not derive_style(PersonalityTraits(confidence=0.9)).hedge


def test_iniciativa_respeita_risco():
    """Iniciativa alta age sozinha em coisa inofensiva, mas RISCO sempre barra —
    ação arriscada é permissão, não personalidade."""
    from aila.mind import should_take_initiative

    ousada = PersonalityTraits(initiative=0.9)
    timida = PersonalityTraits(initiative=0.1)
    assert should_take_initiative(ousada, risk=0.0)        # olhar/comentar: ok
    assert not should_take_initiative(timida, risk=0.0)
    assert not should_take_initiative(ousada, risk=0.8)    # apagar arquivo: nunca


def test_motion_bias_reflete_personalidade():
    from aila.mind import motion_bias

    brincalhona = motion_bias(PersonalityTraits(playfulness=0.95, seriousness=0.1))
    seria = motion_bias(PersonalityTraits(playfulness=0.05, seriousness=0.95))
    assert brincalhona.amplitude > seria.amplitude          # gesticula mais
    for m in (brincalhona, seria):                          # dentro do razoável
        assert 0.6 <= m.amplitude <= 1.35 and 0.7 <= m.speed <= 1.25


def test_erro_tem_tom_de_acordo_com_a_personalidade():
    from aila.mind import error_style

    acolhedora = error_style(PersonalityTraits(empathy=0.9, patience=0.8))
    objetiva = error_style(PersonalityTraits(empathy=0.2, patience=0.2, seriousness=0.9))
    assert acolhedora != objetiva
    assert "http" not in (acolhedora + objetiva).lower()     # erro técnico não vaza na fala


def test_self_expoe_estilo_e_prompt_continua_curto():
    eu = AilaSelf.load()
    st = eu.style()
    assert st.directives
    assert eu.motion().amplitude > 0
    bloco = eu.prompt_block()
    assert any(d in bloco for d in st.directives)            # estilo entrou no prompt
    assert len(bloco) < 700                                  # ainda cabe em num_ctx 8k


# ------------------------------------ Fase D: ciclo corpo -> mente (body.report) #

def _engine_fake():
    """Engine mínimo p/ testar o bloco de corpo sem subir LLM/WS."""
    from aila.core.engine import AilaEngine
    e = object.__new__(AilaEngine)
    e.self_model = AilaSelf.load()
    return e


def test_bloco_de_corpo_so_entra_quando_ha_relato():
    e = _engine_fake()
    assert e._body_block() == ""                       # sem relato → não inventa nada
    e.self_model.update_body(hands={"left": "rest", "right": "raised"})
    bloco = e._body_block()
    assert "estou com a mão direita levantada" in bloco
    assert "nunca diga 'o avatar'" in bloco


def test_bloco_de_corpo_expira(monkeypatch):
    """Corpo velho não pode virar afirmação falsa ('estou apontando' depois de
    ter abaixado o braço) — melhor não saber do que mentir."""
    import time as _t
    e = _engine_fake()
    e.self_model.update_body(hands={"left": "rest", "right": "raised"})
    assert e._body_block() != ""
    agora = _t.time()
    monkeypatch.setattr("aila.core.engine.time.time", lambda: agora + 999)
    assert e._body_block() == ""                       # expirou → silêncio


def test_ciclo_completo_report_ate_o_prompt():
    """CASO OBRIGATÓRIO: report do avatar -> BodyState -> texto em 1ª pessoa."""
    e = _engine_fake()
    # o que o frontend manda (ui/avatar3d.html: readBodyState)
    report = {
        "posture": "standing", "gesture": "raise_right",
        "hands": {"left": "rest", "right": "raised"},
        "gaze_target": "", "interaction_target": "", "interaction_action": "",
    }
    e.self_model.update_body(**report)
    bloco = e._body_block()
    assert "estou" in bloco.lower()
    assert "o avatar está" not in bloco.lower()        # jamais 3ª pessoa
    st = e.self_model.state()
    assert st.body.hands["right"] == "raised" and st.body.gesture == "raise_right"


def test_report_de_interacao_vira_primeira_pessoa():
    e = _engine_fake()
    e.self_model.update_body(gaze_target="o gráfico", interaction_target="o gráfico",
                             interaction_action="apontando para")
    bloco = e._body_block()
    assert "estou olhando para o gráfico" in bloco
    assert "estou apontando para o gráfico" in bloco


def test_report_parcial_nao_quebra():
    """O frontend pode mandar campos faltando/nulos — não pode derrubar nada."""
    e = _engine_fake()
    e.self_model.update_body(hands=None, gesture=None, posture="thinking")
    assert e.self_model.body.posture == "thinking"
    assert e.self_model.body.hands == {"left": "rest", "right": "rest"}


# ------------------------------------- Fase K: Response Validator (identidade) #

def test_validator_corrige_terceira_pessoa():
    """CASO OBRIGATÓRIO (item 31/24): body diz mão levantada e a resposta sai em
    3ª pessoa → o validador corrige sozinho, sem LLM."""
    from aila.mind.response_validator import validate

    r = validate("O avatar está com a mão direita levantada.")
    assert not r.ok and r.has("self_reference") and r.changed
    assert r.text == "Estou com a mão direita levantada."
    assert "avatar" not in r.text.lower()


def test_validator_varios_sujeitos_e_verbos():
    from aila.mind.response_validator import validate

    assert validate("o modelo levantou o braço").text == "levantei o braço"
    assert validate("A Aila está analisando o gráfico.").text == "Estou analisando o gráfico."
    assert validate("o personagem apontou para a tela").text == "apontei para a tela"


def test_validator_nao_arrisca_verbo_desconhecido():
    """Reescrever errado ('eu cambaleou') é pior que a violação: se o verbo não
    está na tabela, mantém o texto — mas ainda assim não inventa correção."""
    from aila.mind.response_validator import validate

    r = validate("o avatar cambaleou pela sala")
    assert r.text == "o avatar cambaleou pela sala"
    assert not r.changed


def test_validator_pega_negacao_de_capacidade():
    """O erro REAL: pediram 'levante os braços' e ela disse que não faz tarefas
    físicas — tendo corpo e ferramenta de gesto."""
    from aila.mind.response_validator import correction_hint, validate

    class _T:
        def __init__(self, n): self.name = n

    class _Reg:
        def all(self): return [_T("avatar.gesture")]

    eu = AilaSelf.load()
    eu.bind_capabilities(_Reg())
    r = validate("Como assistente de IA baseado em texto, não consigo realizar tarefas físicas.",
                 self_model=eu)
    assert r.has("capability_denial")
    assert "corpo" in correction_hint(r).lower()

    # sem controle de corpo registrado, a negação é LEGÍTIMA (não é violação)
    class _Vazio:
        def all(self): return []
    sem = AilaSelf.load()
    sem.bind_capabilities(_Vazio())
    assert not validate("não consigo realizar tarefas físicas", self_model=sem).has("capability_denial")


def test_validator_narracao_do_sistema_depende_do_assunto():
    from aila.mind.response_validator import validate

    fala = "O Behavior Planner decidiu levantar o braço."
    assert validate(fala).has("system_narration")           # conversa normal: violação
    assert not validate(fala, allow_technical=True).has("system_narration")  # falando de arquitetura: ok


def test_validator_nao_estraga_resposta_boa():
    """Falso positivo é o pior defeito de um validador: não pode mexer no que
    já está certo."""
    from aila.mind.response_validator import validate

    for boa in ("Assim? Levantei a mão direita.",
                "Estou olhando para o gráfico agora.",
                "Pronto! Salvei em Documentos.",
                "O sistema operacional é o Windows 11."):
        r = validate(boa)
        assert r.text == boa and not r.changed, boa


# ------------------------------------------- Fase E: experiência atual (o agora) #

def test_atividade_vem_da_ferramenta_usada():
    """A atividade é derivada do que ela REALMENTE executou — não de adivinhação
    sobre o texto da resposta."""
    from aila.mind.experience import activity_for_tool, activity_for_tools

    assert activity_for_tool("web.search") == "searching"
    assert activity_for_tool("code.test") == "testing"
    assert activity_for_tool("code.write_file") == "coding"
    assert activity_for_tool("file.read") == "reading"
    assert activity_for_tool("ferramenta.inexistente") is None
    # a ÚLTIMA reconhecida vence: é o que está acontecendo agora
    assert activity_for_tools(["web.search", "web.fetch"]) == "reading"
    assert activity_for_tools([]) == "idle"


def test_experiencia_descreve_em_primeira_pessoa():
    from aila.mind.experience import describe

    assert describe("searching") == "estou pesquisando"
    assert describe("analyzing", "o gráfico") == "estou analisando (o gráfico)"
    assert describe("idle") == ""                      # nada a dizer não polui o prompt
    assert "avatar" not in describe("coding").lower()


def test_bloco_junta_atividade_e_corpo():
    e = _engine_fake()
    e.self_model.update_experience(activity="analyzing", attention="o gráfico")
    e.self_model.update_body(gaze_target="o gráfico")
    bloco = e._body_block()
    assert "estou analisando" in bloco and "estou olhando para o gráfico" in bloco
    assert "[VOCÊ AGORA]" in bloco


def test_atividade_sobrevive_ao_corpo_expirado(monkeypatch):
    """Corpo velho é descartado (postura passada seria mentira), mas a atividade
    do turno continua válida — ela é sempre do agora."""
    import time as _t
    e = _engine_fake()
    e.self_model.update_body(hands={"left": "rest", "right": "raised"})
    e.self_model.update_experience(activity="searching")
    agora = _t.time()
    monkeypatch.setattr("aila.core.engine.time.time", lambda: agora + 999)
    bloco = e._body_block()
    assert "estou pesquisando" in bloco               # atividade permanece
    assert "levantada" not in bloco                    # postura antiga não é afirmada


# --------------------------------------------- Fase G: Context Manager (orçamento) #

def test_orcamento_escala_com_a_janela_e_o_provedor():
    from aila.mind.context_manager import budget_for

    pequeno = budget_for(8192, local=True)      # modelo local: janela apertada
    grande = budget_for(128000, local=False)    # nuvem: cabe mais
    assert 0 < pequeno < grande
    assert budget_for(8192, local=False) > pequeno   # mesma janela, mais folga na nuvem
    assert budget_for(0, local=True) > 0              # nunca zero (config torta)


def test_estado_tem_prioridade_sobre_memoria():
    """Quando aperta, o que sobrevive é o ESTADO (evita a 3ª pessoa); a memória
    é a primeira a ser cortada."""
    from aila.mind.context_manager import build_blocks

    estado = "[VOCÊ AGORA] estou com a mão direita levantada."
    memoria = "M" * 5000
    blocos = build_blocks(state_block=estado, memory_block=memoria, budget_chars=len(estado) + 200)
    assert blocos[0] == estado                        # estado intacto
    assert len(blocos[1]) < len(memoria)              # memória cortada p/ caber


def test_memoria_sai_inteira_quando_ha_espaco():
    from aila.mind.context_manager import build_blocks

    blocos = build_blocks(state_block="estado", memory_block="memoria", budget_chars=10_000)
    assert blocos == ["estado", "memoria"]


def test_memoria_e_descartada_se_nao_couber():
    from aila.mind.context_manager import build_blocks

    estado = "E" * 300
    blocos = build_blocks(state_block=estado, memory_block="lembrança importante",
                          budget_chars=310)
    assert blocos == [estado]                          # nada de meia-memória inútil


def test_blocos_vazios_nao_poluem():
    from aila.mind.context_manager import build_blocks

    assert build_blocks(state_block="", memory_block="", budget_chars=1000) == []
    # memória SOZINHA é contexto legítimo (sem corpo, mas com lembrança útil)
    assert build_blocks(state_block="  ", memory_block="x" * 90, budget_chars=1000) == ["x" * 90]


def test_identidade_igual_no_caminho_casual_e_no_normal():
    """Item 23: a Aila é a MESMA nos dois caminhos (papo x tarefa)."""
    from aila.core.engine import AilaEngine

    e = object.__new__(AilaEngine)
    e.self_model = AilaSelf.load()
    e.settings = type("S", (), {"app": type("A", (), {"persona": "fallback"})()})()
    casual = e._casual_prompt()
    assert "Aila" in casual and "primeira pessoa" in casual.lower()
    # mesmas diretivas de estilo do self model (não um texto paralelo)
    assert any(d in casual for d in e.self_model.style().directives)


# ------------------------------------------ Fase I: Decision Engine (ação decidida) #

def test_decide_gesto_pelo_pedido_nao_pelo_texto():
    """A ação passa a vir do PEDIDO (determinístico), não da inferência sobre a
    resposta — assim o corpo se mexe mesmo se o modelo esquecer a ferramenta."""
    from aila.mind.decision_engine import decide_gesture

    assert decide_gesture("levante a mão direita") == "raise_right"
    assert decide_gesture("levanta a mao esquerda") == "raise_left"
    assert decide_gesture("levante as mãos") == "raise_both"      # plural = os dois
    assert decide_gesture("levanta a mão") == "raise_right"       # sem lado = dominante
    assert decide_gesture("acene para mim") == "wave"
    assert decide_gesture("aponte para a tela") == "point"
    assert decide_gesture("abaixe os braços") == "rest"


def test_decide_so_age_no_inequivoco():
    """Ambiguidade fica com o LLM: assumir o corpo por engano é pior que não agir."""
    from aila.mind.decision_engine import decide, decide_gesture

    for t in ("oi tudo bem?", "faça um jogo em python", "o que você acha de IA?",
              "me explique como levantar um servidor", ""):
        assert decide_gesture(t) is None, t
        assert decide(t) is None, t


def test_decisao_so_produz_gesto_que_o_avatar_conhece():
    """Decidir um gesto inexistente faria o avatar ignorar em silêncio."""
    from aila.agents.avatar_agent import GESTURES
    from aila.mind.decision_engine import GESTOS_VALIDOS, decide_gesture

    assert GESTOS_VALIDOS == set(GESTURES)          # listas não podem divergir
    for pedido in ("levante a mão direita", "acene", "aponte para lá", "manda joinha"):
        g = decide_gesture(pedido)
        assert g in GESTURES, (pedido, g)


def test_decisao_traz_acao_e_deixa_a_fala_com_o_llm():
    from aila.mind.decision_engine import decide

    eu = AilaSelf.load()
    d = decide("levante a mão direita", self_model=eu)
    assert d is not None
    assert d.actions[0].type == "raise_right"
    assert d.speech.text == ""                       # o texto continua sendo do modelo
    assert d.reason.startswith("user_request")


# ------------------------------- Fase J/L: fala e ação separadas no BehaviorSpec #

def test_acao_decidida_tem_precedencia_sobre_o_texto():
    """A ação vem do PEDIDO; o texto da resposta não pode sobrescrevê-la."""
    from aila.avatar.behavior_planner import BehaviorPlanner

    p = BehaviorPlanner()
    # texto que normalmente induziria outro gesto pela inferência
    spec = p.plan("Claro! Vou pesquisar isso pra você.", actions=["raise_right"])
    assert [g.type for g in spec.gestures] == ["raise_right"]
    assert spec.gestures[0].at_time == 0.0        # no início da fala


def test_sem_acao_decidida_o_comportamento_antigo_permanece():
    """Compatibilidade: sem decisão, segue a inferência pelo texto (nada quebra)."""
    from aila.avatar.behavior_planner import BehaviorPlanner

    p = BehaviorPlanner()
    antes = p.plan("Oi! Tudo bem com você?")
    depois = p.plan("Oi! Tudo bem com você?", actions=[])
    assert [g.type for g in antes.gestures] == [g.type for g in depois.gestures]


def test_personalidade_modula_a_energia_do_movimento():
    """Item 6: a personalidade influencia gestos — sem virar assunto."""
    from aila.avatar.behavior_planner import BehaviorPlanner
    from aila.mind import PersonalityTraits, motion_bias

    p = BehaviorPlanner()
    brincalhona = motion_bias(PersonalityTraits(playfulness=0.95, seriousness=0.1))
    seria = motion_bias(PersonalityTraits(playfulness=0.05, seriousness=0.95))
    a = p.plan("Pronto.", motion_bias=(brincalhona.amplitude, brincalhona.speed, brincalhona.breath))
    b = p.plan("Pronto.", motion_bias=(seria.amplitude, seria.speed, seria.breath))
    assert a.motion.amplitude > b.motion.amplitude
    # o contrato com o frontend NÃO muda de formato
    assert set(a.model_dump()) == set(p.plan("Pronto.").model_dump())


def test_pedido_corporal_gera_gesto_de_ponta_a_ponta():
    """Pedido → decisão → BehaviorSpec, sem passar pelo texto do modelo."""
    from aila.avatar.behavior_planner import BehaviorPlanner
    from aila.mind.decision_engine import decide

    d = decide("levante as mãos", self_model=AilaSelf.load())
    spec = BehaviorPlanner().plan("Assim?", actions=[a.type for a in d.actions])
    assert [g.type for g in spec.gestures] == ["raise_both"]
    assert spec.text == "Assim?"                   # fala preservada, separada da ação
