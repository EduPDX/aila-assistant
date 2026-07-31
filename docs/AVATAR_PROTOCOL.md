# Protocolo do Avatar 3D

O núcleo da Aila não desenha o avatar — ele **dirige** um cliente 3D
(Unreal Engine ou Unity) enviando estados. Isso mantém a IA e o render 3D
desacoplados: você pode trocar a engine 3D sem tocar no núcleo.

## Canal

Estados são emitidos como eventos `avatar.state` pela WebSocket (`/ws`). O
cliente 3D conecta como um consumidor e aplica cada estado recebido.

## Payload: `AvatarState`

Definido em `aila/avatar/protocol.py`:

```json
{
  "emotion": "focused",
  "gesture": "hand_explain",
  "animation": "thinking",
  "speech_state": "talking",
  "intensity": 0.7,
  "viseme": null,
  "text": "Deixa eu pensar nisso..."
}
```

| Campo | Tipo | Valores |
|-------|------|---------|
| `emotion` | enum | neutral, happy, confident, focused, confused, surprised, sad, thinking |
| `gesture` | enum | none, hand_explain, point, thumbs_up, shrug, wave, nod |
| `animation` | enum | idle, thinking, talking, typing, celebrate |
| `speech_state` | enum | silent, talking, listening |
| `intensity` | float | 0.0–1.0 (força da expressão) |
| `viseme` | string? | fonema visual p/ lip-sync (preenchido pelo TTS na Fase 2) |
| `text` | string? | texto associado (legenda/debug) |

## Como o estado é gerado (Emotion Engine)

`aila/avatar/emotion_engine.py` deriva o estado em camadas:

1. **Sinais de fase** — `thinking()` enquanto processa, `listening()` ao ouvir.
2. **Heurística léxica** — palavras-chave no texto da resposta mapeiam para
   emoção + gesto. Exemplos do projeto:
   - `erro / falha / traceback` → `confused` + `shrug`
   - `pronto / resolvido / funcionou` → `happy` + `thumbs_up`
   - `recomendo / solução / proponho` → `confident` + `hand_explain`
3. **(Fase futura)** classificação por LLM leve para nuance emocional.

## Mapeamento sugerido no cliente 3D (Fase 4)

| Protocolo | Unreal/Unity |
|-----------|--------------|
| `emotion` | Blend shape / morph target facial + peso = `intensity` |
| `gesture` | Montagem de animação de braço/mão (upper-body slot) |
| `animation` | State machine do corpo (idle/talk/think loops) |
| `speech_state=talking` | Ativa lip-sync; `listening` → pose de escuta |
| `viseme` | Curva de blend shape de boca (lip-sync fino) |

## Exemplo de consumidor (pseudo)

```csharp
// Unity — WebSocket onMessage
var s = JsonUtility.FromJson<AvatarState>(msg);
face.SetEmotion(s.emotion, s.intensity);
if (s.gesture != "none") anim.PlayGesture(s.gesture);
body.SetState(s.animation);
lipSync.enabled = (s.speech_state == "talking");
```
