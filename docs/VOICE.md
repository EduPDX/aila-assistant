# Sistema de Voz

A Aila **ouve** (STT) e **fala** (TTS), permitindo conversa natural por voz.

```
🎙 microfone → grava (detecção de silêncio) → /api/voice/transcribe (Whisper)
   → texto vira mensagem → engine responde → /api/voice/speak (TTS) → 🔊 áudio
   → (modo conversa) volta a ouvir automaticamente
```

## Saída de voz — TTS (a Aila fala)

Três engines, escolhidas em `config → voice.tts.engine`:

| Engine | Qualidade | Dependências | Observação |
|--------|-----------|--------------|------------|
| **sapi** | boa | **nenhuma** | System.Speech do Windows; voz pt-BR nativa (ex.: "Microsoft Maria"). **Funciona de imediato.** |
| **piper** | ótima (neural) | `pip install -e ".[piper]"` + modelo | Vozes neurais offline. |
| **auto** | — | — | Usa Piper se instalado, senão SAPI. |

Por padrão (`auto` → SAPI), a Aila já fala em português sem instalar nada.
Se não houver voz pt-BR e nenhuma configurada, o SAPI seleciona a primeira voz
pt-* instalada automaticamente; ajuste com `voice.tts.voice` (nome exato da voz).

> Vozes pt-BR extras podem ser adicionadas em *Configurações do Windows →
> Hora e idioma → Fala*.

## Entrada de voz — STT (a Aila ouve)

`faster-whisper` (CTranslate2). Na **RTX 4060** roda em CUDA/float16; se as libs
CUDA (cuBLAS/cuDNN) não estiverem presentes, **cai para CPU/int8 automaticamente**.

- Instalação: `pip install -e ".[voice]"`
- Modelo: `voice.stt.model` (`tiny` < `base` < `small` < `medium`). Baixado do
  HuggingFace na 1ª execução.
- O áudio do navegador (webm/opus) é decodificado pelo PyAV — sem conversão manual.

## Usando na interface

| Controle | Ação |
|----------|------|
| 🎙 (composer) | Clique e fale; para sozinho após ~1,2 s de silêncio, transcreve e envia |
| 🔊 / 🔇 (topo) | Liga/desliga a Aila falar as respostas |
| 🎧 (topo) | **Modo conversa**: mãos livres — após falar, ela volta a te ouvir |

O microfone exige contexto seguro; `http://localhost` já conta como seguro.

## API

| Rota | Método | Descrição |
|------|--------|-----------|
| `/api/voice/status` | GET | Engines disponíveis e config |
| `/api/voice/transcribe` | POST (multipart `file`) | Áudio → texto |
| `/api/voice/speak` | POST (`{"text"}`) | Texto → `audio/wav` |

## Configuração (`config → voice`)

```yaml
voice:
  enabled: true
  stt:  { engine: faster-whisper, model: base, language: pt, device: auto }
  tts:  { engine: auto, voice: "", rate: 0, output_enabled: true }
```

## Roadmap da voz
- [ ] Síntese por frase durante o streaming (latência menor na fala)
- [ ] XTTS (clonagem de voz) como engine premium
- [ ] Visemes do TTS → lip-sync do avatar 3D (Fase 4)
