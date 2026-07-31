# Arquitetura da Aila

Este documento descreve como as peças da Aila se encaixam. O princípio central
é **modularidade com baixo acoplamento**: cada módulo é substituível e se comunica
por interfaces bem definidas e por um **barramento de eventos**.

## Visão em camadas

```
┌─────────────────────────────────────────────────────────────┐
│  APRESENTAÇÃO                                                 │
│  ui/index.html  ·  (fase 4) Avatar 3D Unreal/Unity           │
└───────────────┬─────────────────────────────┬───────────────┘
                │ WebSocket /ws               │ WebSocket avatar.state
┌───────────────▼─────────────────────────────▼───────────────┐
│  API  (aila/api)                                             │
│  routes.py (REST)  ·  websocket.py (tempo real + permissões) │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│  ORQUESTRAÇÃO  (aila/core)                                   │
│  engine.py  ·  context.py  ·  event_bus.py  ·  config.py     │
└───┬───────────┬───────────┬───────────┬─────────────────────┘
    │           │           │           │
┌───▼───┐  ┌────▼─────┐ ┌───▼────┐  ┌───▼──────────────────────┐
│  LLM  │  │  AGENTS  │ │ AVATAR │  │  SEGURANÇA               │
│aila/  │  │ aila/    │ │ aila/  │  │  aila/security           │
│llm    │  │ agents   │ │ avatar │  │  permissions·sandbox·    │
│       │  │ +tools   │ │ emotion│  │  audit                   │
└───────┘  └──────────┘ └────────┘  └──────────────────────────┘
      │           │
┌─────▼───────────▼───────────────────────────────────────────┐
│  RECURSOS EXTERNOS                                           │
│  Ollama / llama.cpp  ·  Sistema de arquivos  ·  SO (Win API) │
└─────────────────────────────────────────────────────────────┘
```

## Fluxo de uma mensagem (modo chat)

1. A UI envia `{"type":"user.message","text":...,"mode":"chat"}` pela WebSocket.
2. `websocket.py` chama `engine.process(text, emit, mode)`.
3. A engine emite `avatar.state` (pensando), adiciona a mensagem ao `context`,
   e chama o `LLMBackend.chat(...)` em **streaming**.
4. Cada token vira um evento `assistant.token` → aparece na UI em tempo real.
5. Ao final, a engine deriva o estado do avatar (`EmotionEngine.from_text`) e
   emite `assistant.message` + `avatar.state`.

## Fluxo de uma mensagem (modo agente)

1. Igual até a engine, mas ela chama `run_agentic`.
2. `LLMBackend.chat_message(..., tools=schemas)` decide se usa ferramentas.
3. Para cada `tool_call`: a engine emite `agent.invoked`, executa via
   `ToolRegistry`, que passa pelo `PermissionManager` **antes** de agir.
4. Se a ação for destrutiva, `permissions.py` dispara `permission.request` →
   a UI mostra o modal → a resposta volta como `permission.response`.
5. O resultado vira `agent.result` e realimenta o modelo, até ele responder.

## Componentes-chave

| Módulo | Arquivo | Papel |
|--------|---------|-------|
| Config | `core/config.py` | Config em camadas (YAML + env), tipada com Pydantic |
| Event Bus | `core/event_bus.py` | Pub/sub assíncrono entre módulos |
| Contexto | `core/context.py` | Janela de conversa + sumarização |
| Engine | `core/engine.py` | Orquestra LLM + agentes + avatar |
| LLM | `llm/*` | Backends plugáveis (Ollama; llama.cpp na fase 2) |
| Agentes | `agents/*` | File, Code, Computer, Vision, Binary |
| Tools | `tools/*` | Contrato de ferramentas (JSON Schema) |
| Segurança | `security/*` | Permissões, sandbox, auditoria |
| Avatar | `avatar/*` | Protocolo `AvatarState` + Emotion Engine |
| API | `api/*` | REST + WebSocket |

## Por que essas escolhas

- **Ollama como backend inicial**: abstrai o carregamento de GGUF, o offload
  CUDA na RTX 4060 e o gerenciamento de VRAM — muito menos atrito que integrar
  `llama.cpp` na mão. A interface `LLMBackend` deixa a porta aberta para trocar.
- **Event bus + emit callback**: a engine não conhece WebSocket, HTTP ou a
  engine 3D. Isso permite plugar o avatar Unreal, um app desktop ou testes sem
  tocar no núcleo.
- **Tools com JSON Schema**: compatível com o tool-calling nativo do Ollama e,
  ao mesmo tempo, com um protocolo textual de fallback para modelos sem suporte.
- **Segurança como camada obrigatória**: nenhum agente escreve/executa sem
  passar pelo `PermissionManager`. Ver [SECURITY.md](SECURITY.md).

## Extensão: como adicionar um novo agente

1. Crie `aila/agents/meu_agent.py` herdando de `BaseAgent`.
2. Implemente `tools()` retornando objetos `Tool` (namespace `meu.acao`).
3. Registre a classe em `AGENT_CLASSES` (`agents/manager.py`).
4. Habilite em `config/default.yaml → agents.enabled`.
