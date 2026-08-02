# ============================================================================
#  Receptor de Avatar da Aila — roda DENTRO do Unreal Engine (Python).
#  NÃO é executado pelo Python da Aila; roda no interpretador do editor.
#
#  O que faz: consulta o estado do avatar da Aila (GET /api/avatar/current)
#  ~5x/s e faz a personagem Hayakawa tocar a animação correspondente à emoção
#  ou ao gesto — sem Blueprint e sem OSC.
#
#  COMO USAR (no Unreal):
#    1. Edit > Plugins > habilite "Python Editor Script Plugin" e reinicie.
#    2. Coloque a personagem (BP_Character) no nível.
#    3. Tools > Execute Python Script... e escolha ESTE arquivo
#       (ou cole o conteúdo no console Python do Output Log).
#    4. Do lado da Aila: rode o servidor (python -m aila.main). Teste com:
#         curl -X POST "http://127.0.0.1:8770/api/avatar/test?emotion=happy"
#       A personagem deve reagir. Pare com: aila_stop() (no console Python).
# ============================================================================
import json
import urllib.request

import unreal

# --------------------------- configuração ----------------------------------
AILA_URL = "http://127.0.0.1:8770/api/avatar/current"
TARGET_LABEL = "BP_Character"          # rótulo do ator da personagem no nível
POLL_INTERVAL = 0.2                    # segundos entre consultas (~5x/s)
GESTURE_HOLD = 2.5                     # segundos que um gesto toca antes de voltar ao idle
ANIM = "/Game/CiciToonCharacterShaderPak/Character/Hayakawa/Anim/"

# emoção -> animação de idle (em loop)
EMO_ANIM = {
    "happy":     "Anim_Breathy_Happy",
    "confident": "Anim_Breathy_Happy",
    "surprised": "Anim_Breathy_Happy",
    "sad":       "Anim_Breathy_UnHappy",
    "confused":  "Anim_Breathy_UnHappy",
    "focused":   "Anim_Breathy",
    "thinking":  "Anim_Breathy",
    "neutral":   "Anim_Breathy",
}
# gesto -> animação one-shot
GEST_ANIM = {
    "wink":         "Anim_Wink",
    "nice":         "Anim_Nice",
    "thumbs_up":    "Anim_Nice",
    "hand_explain": "Anim_Nice",
    "nod":          "Anim_Quan",
    "point":        "Anim_Quan",
    "wave":         "Anim_Quan",
    "shrug":        "Anim_Doodle",
}

# --------------------------- estado interno --------------------------------
_S = {"acc": 0.0, "key": None, "mesh": None, "resume": 0.0, "emotion": "neutral"}


def _find_mesh():
    if _S["mesh"] is not None:
        return _S["mesh"]
    subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsys.get_all_level_actors()
    # 1ª tentativa: rótulo exato; 2ª: qualquer esqueleto "Hayakawa"
    for want_exact in (True, False):
        for actor in actors:
            label = actor.get_actor_label()
            if want_exact and label != TARGET_LABEL:
                continue
            comp = actor.get_component_by_class(unreal.SkeletalMeshComponent)
            if comp and ("Hayakawa" in label or "Character" in label):
                _S["mesh"] = comp
                unreal.log("AILA >> personagem encontrada: %s" % label)
                return comp
    return None


def _play(name, looping):
    mesh = _find_mesh()
    if not mesh:
        return
    asset = unreal.load_asset(ANIM + name)
    if asset:
        mesh.play_animation(asset, looping)


def _apply(state):
    emotion = state.get("emotion", "neutral")
    gesture = state.get("gesture", "none")
    _S["emotion"] = emotion
    if gesture and gesture in GEST_ANIM:
        _play(GEST_ANIM[gesture], False)          # gesto: toca uma vez
        _S["resume"] = GESTURE_HOLD               # e agenda voltar ao idle
    else:
        _play(EMO_ANIM.get(emotion, "Anim_Breathy"), True)


def _tick(delta):
    # volta ao idle depois que um gesto terminou
    if _S["resume"] > 0.0:
        _S["resume"] -= delta
        if _S["resume"] <= 0.0:
            _play(EMO_ANIM.get(_S["emotion"], "Anim_Breathy"), True)

    _S["acc"] += delta
    if _S["acc"] < POLL_INTERVAL:
        return
    _S["acc"] = 0.0
    try:
        raw = urllib.request.urlopen(AILA_URL, timeout=0.15).read()
        state = json.loads(raw).get("state")
    except Exception:
        return                                     # Aila offline: ignora
    if not state:
        return
    key = (state.get("emotion"), state.get("gesture"))
    if key != _S["key"]:
        _S["key"] = key
        _apply(state)


def aila_stop():
    """Para o receptor (chame no console Python do Unreal)."""
    h = globals().get("_aila_handle")
    if h:
        unreal.unregister_slate_post_tick_callback(h)
        globals()["_aila_handle"] = None
        unreal.log("AILA >> receptor parado.")


# (re)inicia o loop de tick do editor
if globals().get("_aila_handle"):
    aila_stop()
_aila_handle = unreal.register_slate_post_tick_callback(_tick)
unreal.log("AILA >> receptor de avatar ATIVO — consultando %s" % AILA_URL)
