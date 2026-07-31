# Avatar 3D (Fase 4)

Este diretório hospedará o projeto **Unreal Engine 5** (ou Unity) do avatar da
Aila. Ele é um **cliente** que consome o protocolo `AvatarState` do núcleo.

## Plano

- Cliente WebSocket que conecta em `ws://127.0.0.1:8770/ws` e escuta
  eventos `avatar.state`.
- Personagem com:
  - corpo 3D + state machine de animação (idle/thinking/talking),
  - blend shapes faciais para as emoções,
  - biblioteca de gestos mapeada ao enum `Gesture`,
  - lip-sync por visemes (alimentado pelo TTS na Fase 2).

## Contrato

O formato das mensagens está em [`../docs/AVATAR_PROTOCOL.md`](../docs/AVATAR_PROTOCOL.md)
e a definição canônica em `aila/avatar/protocol.py`.

> Binários de engine (Unreal/Unity) **não** são versionados — ver `.gitignore`.
> Só o projeto/fonte entra no repositório quando esta fase começar.
