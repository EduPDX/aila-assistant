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
