# Avatar 3D no Unreal Engine (personagem Hayakawa via OSC)

Guia para usar um personagem 3D do Unreal (ex.: **CiciToonCharacterShaderPak /
Hayakawa**, UE 5.4) como avatar da Aila, dirigido em tempo real por **OSC**.

```
Aila (engine) --OSC--> Unreal (OSC Server) --> Animation Blueprint + Control Rig
   emoção/gesto/animação/fala                    expressão facial + corpo + cabelo
```

## Por que a Hayakawa serve bem

O pacote já traz o essencial (confirmado nos assets):

| Asset | Papel |
|-------|-------|
| `SK/SKM_Hayakawa`, `PH_Hayakawa` | Malha, esqueleto, física |
| `ABP_Hayakwa` | Animation Blueprint (máquina de estados) |
| `CR_Hayakawa_Morth` | **Control Rig de morph = expressões faciais** |
| `Anim_Breathy`, `Anim_Breathy_Happy`, `Anim_Breathy_UnHappy` | Idle emocional |
| `Anim_Wink`, `Anim_Nice`, `Anim_Quan`, `Anim_Doodle` | Gestos one-shot |
| KawaiiPhysics + SPCRJointDynamics | Balanço de cabelo e saia |

## 1. Lado da Aila

```powershell
pip install -e ".[avatar]"      # instala python-osc
```

Em `config/local.yaml` (ou `.env`):

```yaml
avatar:
  transport: "both"    # navegador + Unreal ("osc" = só Unreal)
  osc_host: "127.0.0.1"
  osc_port: 8000
```

Pronto — a Aila passa a enviar OSC a cada mudança de estado. Confira o último
estado em `GET /api/avatar/current`.

## 2. Contrato OSC (o que a Aila envia)

| Endereço | Tipo | Valores |
|----------|------|---------|
| `/aila/emotion` | string | neutral, happy, confident, focused, confused, surprised, sad, thinking |
| `/aila/gesture` | string | wink, nice, point, thumbs_up, wave, nod, hand_explain, shrug (só quando há gesto) |
| `/aila/animation` | string | idle, thinking, talking, typing, celebrate |
| `/aila/speech` | string | silent, talking, listening |
| `/aila/intensity` | float | 0.0 – 1.0 (peso da expressão) |
| `/aila/text` | string | legenda opcional |

## 3. Lado do Unreal (passo a passo)

### 3.1 Plugins
Edit → Plugins → habilite **OSC**, **KawaiiPhysics** e **SPCR Joint Dynamics**.
Reinicie o editor.

### 3.2 Colocar a personagem
Arraste `Blueprints/Pawn/BP_Character` (Hayakawa) para um nível, ou use o nível
de demo do pacote.

### 3.3 Ator receptor de OSC (`BP_AilaReceiver`)
Crie um **Actor Blueprint**:

1. **BeginPlay** → nó **Create OSC Server** (Address `0.0.0.0`, Port `8000`,
   Start Listening = true). Guarde a referência.
2. Faça **Bind Event to On Osc Message Received**.
3. No evento, pegue o **Address Pattern** (Get OSC Message Address) e leia o
   argumento (Get OSC Message String/Float — o 1º elemento).
4. **Switch on String** pelo endereço e escreva em variáveis do personagem
   (ver 3.4). Ex.: `/aila/emotion` → set `Emotion` (Name/enum);
   `/aila/gesture` → dispara montagem; `/aila/intensity` → set `Intensity`.

> Dica: exponha essas variáveis na personagem (ou numa **Blueprint Interface**
> `BPI_Avatar` com eventos `SetEmotion`, `PlayGesture`, `SetSpeech`) e chame-as
> a partir do receptor. Fica desacoplado e limpo.

### 3.4 Animation Blueprint (`ABP_Hayakwa`)
- **State Machine do corpo**: estado `Idle` reproduz `Anim_Breathy`. Adicione
  transições por `Emotion`:
  - `happy`/`confident` → `Anim_Breathy_Happy`
  - `sad`/`confused` → `Anim_Breathy_UnHappy`
  - demais → `Anim_Breathy`
- **Gestos** (upper body): um **slot de montagem**; ao receber `/aila/gesture`,
  toque a montagem correspondente:
  - `wink` → `Anim_Wink` · `nice`/`thumbs_up` → `Anim_Nice` ·
    `nod`/`point`/`wave` → a que preferir (`Anim_Quan`, `Anim_Doodle`).

### 3.5 Expressão facial (`CR_Hayakawa_Morth`)
No Control Rig de morph, use `Emotion` + `Intensity` para pesar as poses/curvas
de rosto (sorriso, sobrancelhas, olhos). Comece simples:
- `happy` → curva de sorriso = `Intensity`
- `confused` → sobrancelhas assimétricas
- `focused`/`thinking` → olhos semicerrados
- `sad` → cantos da boca para baixo

### 3.6 Lip-sync (fala)
- **Simples (fase 1)**: quando `/aila/speech = talking`, ative um loop de boca
  falando; volte ao normal em `silent`.
- **Real (fase 2)**: quando falar, a personagem baixa e toca o WAV de
  `GET /api/voice/speak` (a Aila também expõe o áudio) e usa um **envelope de
  amplitude** (Audio Analyzer / Synesthesia) para dirigir a abertura da boca —
  o mesmo princípio do lip-sync do avatar do navegador.

## 4. Ajuda ao vivo (Remote Control API)

Abra o projeto e habilite **Edit → Plugins → Remote Control API** (e o
Web Remote Control). Com isso eu consigo, pelo conector Unreal, inspecionar os
morph targets do `SKM_Hayakawa`, posicionar a personagem e ajudar a validar o
fluxo OSC direto no editor.

## 5. Problemas comuns
- **Nada chega**: confira se `osc_port` da Aila == porta do OSC Server no UE, e
  se o firewall do Windows não bloqueia UDP local.
- **Personagem sem física de cabelo**: habilite os plugins KawaiiPhysics/SPCR e
  verifique o Physics Asset da personagem.
- **Ver o que a Aila está mandando**: `GET /api/avatar/current` mostra o último
  estado enviado.
