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
