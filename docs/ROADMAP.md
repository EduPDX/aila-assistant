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
- [ ] Coordenadas de elementos de UI (clicar exatamente onde a visão indicou)
- [ ] **Binary Agent**: integração Ghidra headless (descompilação, chamadas)

## Fase 4 — Avatar 3D

- [ ] Projeto Unreal Engine 5 (ou Unity) em `Avatar/`
- [ ] Cliente que consome `avatar.state` pela WebSocket
- [ ] Blend shapes / morph targets para expressões faciais
- [ ] Lip-sync por visemes vindos do TTS
- [ ] Biblioteca de gestos e animações mapeada ao enum `Gesture`/`Animation`

## Escolhas de modelo para a RTX 4060 8GB

Veja [`config/models.yaml`](../config/models.yaml). Regra de bolso:
- **7B–8B Q4_K_M** cabem 100% na VRAM (rápido).
- **14B** rodam híbrido GPU+CPU (mais lento, mas viável com 32 GB de RAM).
- Rode **um modelo por vez**; o Ollama descarrega da VRAM após `keep_alive`.
