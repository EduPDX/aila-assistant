# Arquitetura da Aila

Este documento descreve como as peças da Aila se encaixam. O princípio central
é **modularidade com baixo acoplamento**: cada módulo é substituível e se comunica
por interfaces bem definidas e por um **barramento de eventos**.

## Visão em camadas

```
┌─────────────────────────────────────────────────────────────┐
│  APRESENTAÇÃO                                                 │
│  ui/app.html (modular)  ·  ui/avatar3d.html (Avatar 3D VRM)  │
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
| Resource Intelligence | `core/hardware.py`, `core/resources.py`, `core/models.py`, `core/oom.py`, `core/context_budget.py`, `core/benchmark.py`, `llm/health.py`, `llm/telemetry.py`, `llm/lifecycle.py`, `llm/model_policy.py` | Mede recursos, escolhe/monitora modelos, previne OOM (ver abaixo) |

### Os quatro "planners" (papéis distintos, nomes parecidos)

Coexistem quatro componentes com "plan/planner" no nome. **Não são
redundantes** — cada um resolve uma coisa diferente:

| Componente | Arquivo | Responsabilidade |
|------------|---------|------------------|
| `BehaviorPlanner` | `avatar/behavior_planner.py` | Decide o COMPORTAMENTO do avatar (emoção/postura/olhar/ritmo/gestos) pelo significado da resposta, antes do TTS. |
| `Planner` | `core/planner.py` | Quebra um objetivo em PASSOS via LLM (e replaneja em falha), para tarefas autônomas longas. |
| `PlanManager` | `core/plan_manager.py` | Ciclo de vida de um PLANO no modo `plan` — propor → aprovar/rejeitar → executar passo a passo. |
| `TaskManager` | `core/tasks.py` | Estado/progresso/cancelamento das TAREFAS em execução (não planeja; acompanha). |

Regra mental: `Planner` = *o que fazer*, `PlanManager` = *aprovar e conduzir*,
`TaskManager` = *acompanhar a execução*, `BehaviorPlanner` = *como o corpo reage*.

## Resource Intelligence (consciência de recursos)

A Aila **orquestra** recursos e modelos — ela não faz inferência (isso é do Ollama).
A regra de ouro é **medir do real** e **orçar antes de agir**, inspirada no
`kimi-k3-in-c`. Um laço de três tempos, todos aditivos e read-only por padrão:

```
MEDIR                        DECIDIR                         AGIR
HardwareMonitor (nvidia-smi  ResourceManager → pressão       model_policy (degrada p/ o
+ psutil, injetável p/ CI)   unificada GPU+RAM               modelo local pequeno sob pressão)
ModelManager (papel/estado/  health (circuit-breaker por     oom.decide_load (shrink/proceed)
footprint via /api/ps,tags)  provedor: cooldown/recuperação) lifecycle (keep_alive adaptativo)
telemetry (tps/TTFT/fallback)context_budget (schemas de      engine adia consolidação de fundo
benchmark (escada medida)    tools contam na janela)         e modera a proatividade sob pressão
```

| Módulo | Papel |
|--------|-------|
| `core/hardware.py` | **Porta única** para o hardware: GPU via `nvidia-smi` (cacheado) e CPU/RAM via `psutil`. Sonda injetável → CI nunca depende de GPU. |
| `core/resources.py` | Junta GPU+RAM num `ResourceSnapshot` e traduz para uma **pressão** comum `NORMAL/ELEVATED/HIGH/CRITICAL` (a pior das duas). |
| `core/models.py` | Inventário dos modelos: papel (chat/code/vision/embed/fast), instalado, carregado, footprint (VRAM) e expiração (keep_alive). |
| `llm/health.py` | Circuit-breaker por provedor (saúde **entre** turnos): falhas seguidas → cooldown; half-open → recupera. O router pula quem está em cooldown, **sem** remover o fallback local. |
| `llm/model_policy.py` | Sob pressão de GPU, escolhe o modelo local **pequeno** — só entre modelos locais, nunca troca de provedor. |
| `core/oom.py` | Pré-voo geral `decide_load`/`can_load`: cabe? → `proceed`/`shrink`. Generaliza o antigo pré-voo da visão. |
| `core/context_budget.py` | Orça a janela por componente e **desconta o custo real dos schemas de ferramentas** do histórico (antes invisível). |
| `llm/telemetry.py` | Desempenho por modelo (tokens/s, TTFT, taxa de fallback), por EWMA. |
| `llm/lifecycle.py` | `keep_alive` adaptativo: encolhe a permanência do modelo conforme a pressão de VRAM. |
| `core/benchmark.py` | Benchmark sob demanda (`python -m aila.core.benchmark`) — a "escada" de modelos medida do real. Fora do hot-path. |

Diagnóstico consolidado em `GET /api/resources` (aba **Recursos** no Inspector).
**Privacidade > recurso**: falta de VRAM nunca vira envio para a nuvem.

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
