# Roadmap

A Aila é entregue em fases. Cada fase é utilizável por conta própria — nada de
"big bang". O que está marcado ✅ já funciona neste repositório.

## Fase 1 — Fundação (ENTREGUE ✅)

- ✅ Estrutura profissional do projeto (pacote `aila`, config, docs)
- ✅ Configuração em camadas (YAML + `.env`, tipada com Pydantic)
- ✅ Barramento de eventos assíncrono
- ✅ Contexto de conversa com janela deslizante
- ✅ Backend de LLM (Ollama) com streaming + tool-calling
- ✅ Sistema de agentes: **File Agent** e **Code Agent** funcionais
- ✅ Segurança: permissões, sandbox de caminhos, auditoria, modo somente-leitura
- ✅ API REST + WebSocket
- ✅ UI web (chat streaming, status, modo agente, confirmação de permissão)
- ✅ Protocolo do avatar (`AvatarState`) + Emotion Engine (heurístico)

## Fase 1.5 — Refinos do núcleo

- ✅ Roteamento automático chat↔agente (a IA decide, tudo em streaming)
- ✅ Persistência de histórico (SQLite) + painel de conversas na UI
- ✅ Memória de longo prazo com embeddings (`nomic-embed-text` + RAG):
  recuperação e gravação automáticas + MemoryAgent (save/search)
- [ ] Backend `llama.cpp` (servidor compatível com API OpenAI)
- [ ] Ampliar cobertura de testes automatizados e CI

## Fase 2 — Voz e controle do computador

- ✅ **Computer Agent** completo: mouse, teclado, atalhos, janelas
  (pygetwindow), captura de tela (mss), comandos PowerShell — com permissões,
  confirmação e auditoria; leitura liberada, atuação gated
- ✅ **STT**: `faster-whisper` (CUDA na RTX 4060, fallback CPU automático)
- ✅ **TTS**: SAPI (Windows, pt-BR nativo, zero deps) + Piper opcional
- ✅ Loop de conversa por voz na UI (microfone com detecção de silêncio +
  modo conversa mãos-livres). Ver [VOICE.md](VOICE.md)
- [ ] Síntese por frase durante o streaming (menor latência de fala)
- [ ] XTTS (clonagem de voz) como engine premium
- [ ] Perfis de permissão por app / lista de apps confiáveis

## Fase 3 — Multimodal e binários

- ✅ **Vision Agent**: LLaVA/Qwen-VL via Ollama — analisar imagem, OCR
  (`vision.read_text`) e interpretar a tela (`vision.screenshot_analyze`);
  upload de imagem na UI (📎) e `/api/upload`
- ✅ **Binary Agent**: triagem (tipo, strings, entropia, cabeçalho PE) +
  descompilação com **Ghidra headless**. Ver [BINARY.md](BINARY.md)
- [ ] Coordenadas de elementos de UI (clicar exatamente onde a visão indicou)

## Fase 4 — Avatar

- ✅ **Avatar visual no navegador** (SVG): consome `avatar.state` em tempo real —
  expressões faciais por emoção, gestos, blink/idle, e **lip-sync real** pela
  amplitude do áudio TTS (WebAudio AnalyserNode). Embutido na UI, sem engine 3D.
- ✅ **Ponte OSC → Unreal Engine**: a Aila transmite o AvatarState via OSC para
  um motor 3D. Guia de montagem com a personagem Hayakawa (UE 5.4) em
  [AVATAR_3D.md](AVATAR_3D.md). Endpoint `GET /api/avatar/current`.
- [ ] Lip-sync 3D via envelope de amplitude do áudio TTS no Unreal
- [ ] Mapeamento fino gesto→montagem e emoção→Control Rig de morph (no editor)

## Resource Intelligence — consciência de recursos (ENTREGUE ✅)

A Aila **entende os próprios recursos** (GPU/VRAM/RAM/modelos) para orquestrar,
monitorar e escolher — **sem virar engine de inferência** (kernels/quantização/
offload seguem responsabilidade do Ollama). Entregue em 12 fatias aditivas
(R1–R12), cada uma testada e isolada. Ver [ARCHITECTURE.md](ARCHITECTURE.md#resource-intelligence-consciência-de-recursos).

- ✅ **R1** `HardwareMonitor` — porta única p/ nvidia-smi + psutil (antes duplicado).
- ✅ **R2** `ResourceManager` — pressão unificada GPU+RAM (NORMAL/ELEVATED/HIGH/CRITICAL).
- ✅ **R3** `ModelManager` — inventário: papel, instalado, carregado, footprint, expiração.
- ✅ **R4** Circuit-breaker de saúde por provedor (cooldown + recuperação half-open).
- ✅ **R5** Roteamento consciente de recurso — sob pressão, degrada p/ o modelo local pequeno.
- ✅ **R6** OOM prevention geral (`decide_load`/`can_load` reusável; generaliza o pré-voo da visão).
- ✅ **R7** Orçamento de contexto explícito — os schemas de ferramentas contam na janela.
- ✅ **R8** Telemetria de desempenho por modelo (tokens/s, TTFT, taxa de fallback).
- ✅ **R9** `keep_alive` **adaptativo** por pressão de VRAM (antes fixo em `10m`).
- ✅ **R10** Comportamento ciente de recurso — adia consolidação de fundo e modera a proatividade.
- ✅ **R11** Painel **Recursos** no Inspector — tudo isso visível (`GET /api/resources`).
- ✅ **R12** Benchmark da "escada" de modelos — medir do real. Roda **no boot** (background +
  cache semanal e pula sob pressão) quando habilitado, ou sob demanda
  (`python -m aila.core.benchmark`); a escada aparece na aba **Recursos**.
  O boot automático é opt-in com `llm.benchmark_on_boot: true` para não disputar
  VRAM nem atrasar a primeira conversa.

**Regra inviolável:** privacidade > recurso — falta de VRAM **nunca** empurra a tarefa
para a nuvem (respeita a `network_policy`).

## Escolhas de modelo para a RTX 4060 8GB

Veja [`config/models.yaml`](../config/models.yaml). Regra de bolso:
- **7B–8B Q4_K_M** cabem 100% na VRAM (rápido).
- **14B** rodam híbrido GPU+CPU (mais lento, mas viável com 32 GB de RAM).
- Rode **um modelo por vez**; o Ollama descarrega da VRAM após `keep_alive` — que
  agora é **adaptativo** (R9): encolhe sob pressão de VRAM para liberar o modelo frio
  mais cedo, e volta ao padrão quando há folga.
