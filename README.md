# Aila — Assistente de IA Local Multimodal para Windows

> Um **agente pessoal de IA** com voz e avatar 3D (VRM) que roda **100% local** no seu PC.
> Capacidades no estilo ChatGPT + Claude Code — conversa, executa tarefas no computador,
> lê e cria documentos, analisa imagens e código — **sem depender de nuvem**, com uma
> camada **cognitiva** (memória, grafo de conhecimento e grafo de código) que faz a Aila
> entender o próprio projeto e os seus.

[![CI](https://github.com/EduPDX/aila-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/EduPDX/aila-assistant/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2011-informational)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## Índice

- [O que é](#o-que-é)
- [Destaques](#destaques)
- [Hardware alvo](#hardware-alvo)
- [Arquitetura](#arquitetura)
- [Cognição — o "subconsciente" da Aila](#cognição--o-subconsciente-da-aila)
- [Avatar 3D (VRM)](#avatar-3d-vrm)
- [Agentes e ferramentas](#agentes-e-ferramentas)
- [Segurança e autonomia](#segurança-e-autonomia)
- [Interface (command-center)](#interface-command-center)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Início rápido](#início-rápido)
- [Rodar do código-fonte (`run.bat`)](#rodar-do-código-fonte-runbat)
- [Desktop (Electron) e build](#desktop-electron-e-build)
- [Offline](#offline)
- [Testes](#testes)
- [Roadmap](#roadmap)
- [Licença](#licença)

---

## O que é

**Aila** é uma assistente de IA local, modular e escalável — pensada para virar um
**Agente Pessoal / "sistema operacional de IA"** local-first. Ela conversa e mantém
contexto, executa tarefas na sua máquina, lê e gera documentos (PDF/Word/Excel/PPT),
analisa imagens e código, fala por voz, e é representada por um **avatar 3D VRM** com
emoções, gestos e sincronização labial.

Tudo roda na sua máquina usando modelos abertos (**Qwen, Llama, DeepSeek Coder,
Mistral**) via **Ollama** e **llama.cpp**. Nenhuma chave de API é obrigatória; quando
você opta por um provedor de nuvem, a chave fica só no backend (nunca no front, nunca
em `localStorage`, nunca no git).

## Destaques

- 🧠 **Camada cognitiva** — memória de longo prazo (RAG), **grafo de conhecimento** que
  cresce das conversas e **grafo de código** (AST) da própria Aila; consolidação em
  background ("dreaming").
- 🗂️ **Projetos** — anexe uma pasta e a Aila constrói um **grafo de código daquele
  projeto**; ao "trabalhar no projeto", as ferramentas dela passam a consultar esse grafo.
- 🎭 **Avatar VRM** com sistema de animação em camadas (emoção → corpo inteiro, gestos por
  IK, auto-colisão, lookAt, lip-sync) sobre **three.js + @pixiv/three-vrm**.
- 🛠️ **Agentes** para arquivos, código, documentos, computador (mouse/teclado/janelas),
  visão (imagens/tela), binários, git e web.
- 🔒 **Segurança de verdade** — níveis de autonomia **L1–L5**, classificação de risco de
  cada ação (SAFE/REVIEW/DANGER/BLOCKED), sandbox de caminhos, orçamento de chamadas,
  denylist de comandos, defesa contra prompt-injection e **log de auditoria** (`audit.jsonl`).
- 🖥️ **UI "command-center"** — chat, avatar em palco, painel de atividade, o 🧠 subconsciente
  (grafos 2D/3D) e configurações dirigidas por schema.
- 📴 **100% offline** — three.js e three-vrm vendorizados; degrada com elegância quando o
  Ollama está fora do ar.

## Hardware alvo

| Componente | Especificação        | Observação                                       |
|------------|----------------------|--------------------------------------------------|
| CPU        | AMD Ryzen 5 5500     | 6 núcleos / 12 threads                            |
| GPU        | NVIDIA RTX 4060 8GB  | Aceleração **CUDA** (llama.cpp/Ollama offload)    |
| RAM        | 32 GB                | Confortável para modelos 7B–14B quantizados       |

> Com 8 GB de VRAM, o ponto ideal são modelos **7B–8B quantizados (Q4_K_M)**, que rodam
> inteiramente na GPU. Modelos 14B rodam em modo híbrido GPU+CPU. Para embeddings da
> memória/grafo, use `nomic-embed-text` (`ollama pull nomic-embed-text`).

## Arquitetura

```
┌──────────────────────────────────────────────────────────────┐
│                      UI (Web / Desktop Electron)               │
│   chat · voz · avatar VRM · 🧠 subconsciente · atividade       │
└───────────────────────────┬──────────────────────────────────┘
                            │ WebSocket / REST
┌───────────────────────────▼──────────────────────────────────┐
│                        AILA CORE ENGINE                        │
│  orquestrador · contexto · roteador de agentes · tools ·       │
│  COGNIÇÃO (memória + grafos) · consolidação em background       │
└──┬────────┬─────────┬─────────┬─────────┬─────────┬───────────┘
   │        │         │         │         │         │
┌──▼──┐ ┌───▼───┐ ┌───▼───┐ ┌───▼────┐ ┌──▼────┐ ┌──▼───────┐
│ LLM │ │Agents │ │ Voice │ │ Vision │ │Avatar │ │ Cognition│
│Ollama│ │file   │ │STT/TTS│ │ LLaVA  │ │VRM    │ │ memory   │
│llama │ │code   │ │Whisper│ │ Qwen-V │ │emotion│ │ kgraph   │
│.cpp  │ │doc    │ │Piper  │ │        │ │gesture│ │ codegraph│
│      │ │computer│ │SAPI  │ │        │ │lipsync│ │ projects │
│      │ │vision…│ │XTTS   │ │        │ │IK     │ │ skills   │
└──────┘ └───────┘ └───────┘ └────────┘ └───────┘ └──────────┘
        todos os módulos se comunicam pelo EVENT BUS interno
```

Detalhes em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Cognição — o "subconsciente" da Aila

A camada cognitiva vive em `aila/cognition/` e é plugada no engine sem substituir nada
do que já existia:

- **Memória** (`aila/memory/` + `cognition/memory/`) — store vetorial (SQLite +
  embeddings) com metadados cognitivos (entidades, importância, confiança, reforço);
  recuperação **híbrida** (vetorial + entidades + traversal do grafo).
- **Grafo de Conhecimento** — cresce das conversas: entidades são extraídas na gravação
  (heurística offline) e refinadas por LLM em background; a **consolidação** liga por
  co-ocorrência ("dreaming" conservador). Reconstruível sob demanda em *Configurações ▸
  Memória ▸ Reconstruir grafo de Conhecimento*.
- **Grafo de Código** — índice AST (módulos/classes/funções + `defines`/`imports`/`calls`)
  da própria Aila, usado pelo Code Agent para navegar ("quem chama X", "impacto de Y").
- **Projetos** — anexe uma pasta local e a Aila constrói o grafo de código **daquele
  projeto** (`data/projects/<slug>/`). Em *🧠 ▸ Projetos*, uma grade mostra cada projeto;
  **"Trabalhar no projeto"** deixa o Code Agent consultar o grafo dele em vez do da Aila.
- **Subconsciente (UI)** — a aba 🧠 visualiza os grafos em **2D e 3D** (cubo wireframe),
  com comunidades, filtro, busca e destaque de vizinhos. Nada de chain-of-thought: só
  estado cognitivo de alto nível.

## Avatar 3D (VRM)

O avatar usa **three.js (r167)** + **@pixiv/three-vrm (v3.x)**, ambos vendorizados
(offline). O sistema de animação é **em camadas aditivas**: cada camada escreve num
`PoseBuffer` e o `Rig` faz o commit final — nenhuma camada destrói a outra.

- **Emoção afeta o corpo inteiro** — expressão facial + postura + olhar + amplitude/
  velocidade de gesto + respiração + abertura de braços (`ui/avatar/profiles.js`).
- **Gestos por IK** (2 ossos, analítico) + **auto-colisão proativa** por cápsulas +
  **limites de junta**; **lookAt** com olhos (three-vrm) e cabeça/tronco (cadeia própria).
- **Lip-sync** por visemes; **spring bones** (cabelo/roupa) nativos do three-vrm.
- Planejador de comportamento no backend (`aila/avatar/`) deriva emoção/gesto/olhar do
  **significado** da resposta (não do áudio).

> Auditoria técnica completa do sistema de avatar + plano de evolução:
> ver o documento de análise em `docs/` / pasta de pesquisa do projeto.

## Agentes e ferramentas

Cada agente expõe ferramentas nomeadas que a IA chama quando decide (roteamento
automático). Toda chamada passa por `authorize()` → classificação de risco → auditoria.

| Agente | O que faz |
|--------|-----------|
| **File** | ler/escrever/mover arquivos (dentro do sandbox) |
| **Code** | ler/editar código, **grafo de código** (mapa, definição, callers/callees, impacto) |
| **Document** | ler e **criar** PDF, Word, Excel, PowerPoint e texto |
| **Computer** | mouse, teclado, janelas, executar comandos (requer autonomia alta) |
| **Vision** | analisar imagens e capturas de tela (LLaVA / Qwen-VL) |
| **Binary** | triagem de binários (+ integração Ghidra) |
| **Git** | operações de repositório |
| **Web** | busca/leitura na web (quando online) |
| **Memory** | consultar/gerenciar a memória de longo prazo |

Namespaces de ferramentas adicionais: **Skills** (receitas nomeadas reutilizáveis) e
**MCP** (servidores externos expostos como ferramentas).

## Segurança e autonomia

A Aila pode controlar o seu computador — então a segurança é levada a sério:

- **Autonomia L1–L5** — do somente-leitura (L1) ao autônomo com tarefas (L4–L5). Ações
  acima do nível são bloqueadas ou pedem confirmação.
- **Classificação de risco** por ação: `SAFE` · `REVIEW` · `DANGER` · `BLOCKED`.
- **Sandbox de caminhos**, **orçamento de chamadas** (CallBudget), **timeouts** de
  ferramenta e **denylist de comandos**.
- **Anti prompt-injection** — conteúdo de memória/ferramentas é tratado como **dado**,
  nunca como instrução (`injection.wrap_external`).
- **Auditoria** de tudo em `audit.jsonl`; **modo somente-leitura**; segredos nunca são
  logados nem expostos ao front (a chave real vive só no backend; `GET /api/config` a
  redige).

Leia [`docs/SECURITY.md`](docs/SECURITY.md) antes de habilitar o Computer Agent.

## Interface (command-center)

A UI é vanilla JS (ES-modules, sem framework/bundler), estética HUD/FUI:

- **Chat** com conversa única (retoma a última + linha do tempo) e **anexos** (arquivos
  soltos → roteados para o Document/Vision Agent).
- **Avatar** em palco, com controle de fala e emoções.
- **🧠 Subconsciente** — grafos de Código / Conhecimento / Projetos (2D e 3D).
- **Atividade** — status, eventos cognitivos, tarefas.
- **Configurações** — dirigidas por schema, mapeadas 1:1 para `config/local.yaml`
  (aparência, modelos, voz, avatar, memória, autonomia, agentes, segurança, rede, sistema).

## Estrutura do projeto

```
aila-assistant/
├── aila/                    # Backend Python (pacote principal)
│   ├── core/                # Engine, event bus, config, contexto
│   ├── llm/                 # Backends de modelos (Ollama, llama.cpp)
│   ├── agents/              # File, Code, Document, Computer, Vision, Binary, Git, Web, Memory, Avatar
│   ├── cognition/           # Camada cognitiva
│   │   ├── memory/          #   consolidação, entidades, retrieval híbrido
│   │   ├── graph/           #   GraphStore, Code Graph (AST), Projetos, view
│   │   └── skills/          #   receitas nomeadas reutilizáveis
│   ├── memory/              # MemoryStore (vetorial) + MemoryManager
│   ├── tools/               # Registro de ferramentas chamáveis pela IA
│   ├── security/            # Permissões, sandbox, auditoria, injection
│   ├── voice/               # STT (Whisper) e TTS (SAPI/Piper/XTTS)
│   ├── vision/              # Análise de imagem / screenshots
│   ├── avatar/              # Behavior planner + emotion engine + protocolo
│   ├── database/            # Persistência (SQLite)
│   └── api/                 # Rotas REST + WebSocket
├── ui/                      # Frontend (ES-modules)
│   ├── js/                  #   core, shell, views, graph (2D/3D)
│   ├── avatar/              #   sistema de animação VRM (layers, solvers)
│   ├── styles/              #   CSS (command-center)
│   └── vendor/              #   three.js + three-vrm (vendorizados, offline)
├── desktop/                 # Empacotamento Electron + PyInstaller
├── config/                  # Configuração YAML (+ local.yaml, gitignored)
├── docs/                    # Arquitetura, roadmap, segurança
├── scripts/                 # Setup e download de modelos (PowerShell)
├── tests/                   # Suíte de testes (pytest)
├── run.bat / run.ps1        # Rodar do código-fonte (dev), sem build
└── data/ · models/          # (gitignored) bancos locais e pesos GGUF
```

## Início rápido

### 1. Pré-requisitos

- Windows 11, Python 3.11+ (testado em 3.14)
- [Ollama](https://ollama.com/download) instalado e rodando (`ollama serve`)
- Drivers NVIDIA + CUDA atualizados
- Modelos: `ollama pull qwen2.5-coder:7b` e `ollama pull nomic-embed-text` (embeddings)

### 2. Instalação (um comando)

```powershell
.\install.ps1                         # base (chat, agentes, avatar, cognição)
```

Com os módulos opcionais que quiser:

```powershell
.\install.ps1 -Extras voice,vision    # + voz (Whisper) e captura de tela
.\install.ps1 -All -PullModels        # tudo + baixa os modelos do Ollama
```

Extras: `voice` (STT Whisper), `piper` (TTS neural), `vision` (captura de tela),
`computer` (controle de mouse/teclado), `dev` (lint/testes). A **saída de voz** (a Aila
falar) já funciona sem extras, via SAPI do Windows.

### 3. Rodar

```powershell
ollama serve                                  # em outro terminal
.\.venv\Scripts\python.exe -m aila.main
```

Abra o endereço mostrado no terminal (porta livre a partir de `8770`).

## Rodar do código-fonte (`run.bat`)

Para desenvolver **sem gerar `.exe`** — o jeito mais rápido de ver mudanças na hora:

```bat
run.bat
```

`run.bat` chama `run.ps1`, que:

- escolhe automaticamente uma **porta livre** (evita conflito com portas reservadas do
  Windows/WSL) e a exporta em `AILA_PORT`;
- sobe o backend do repositório com **reload** (mudanças no Python reiniciam sozinhas);
- abre a Aila no navegador.

Para mudanças no **frontend**, basta recarregar a página (a UI serve com `Cache-Control:
no-cache` em dev). `Ctrl+C` encerra.

## Desktop (Electron) e build

O app desktop empacota **backend (PyInstaller) + frontend + Electron** num executável.
O build **pré-constrói o grafo de código** (`code_graph.prebuilt.db`) porque o `.exe` não
carrega os fontes `.py`. Scripts em `desktop/` (`build.ps1`, `prebuild_graph.py`).

O Electron desabilita o cache HTTP (`disable-http-cache` + `clearCache`) para nunca
mostrar uma UI antiga após atualizar.

## Offline

- `three.js` e `@pixiv/three-vrm` são **vendorizados** em `ui/vendor/` — nada de CDN.
- Sem Ollama, a Aila **degrada com elegância**: a extração de entidades cai para a
  heurística offline, a memória segue gravando, e a UI continua utilizável.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

## Roadmap

Fases entregues e próximas em [`docs/ROADMAP.md`](docs/ROADMAP.md).

| Fase | Módulo                                             | Status        |
|------|----------------------------------------------------|---------------|
| 1    | Core engine + event bus + config                   | ✅ funcional  |
| 1    | LLM backend (Ollama) + agentes File/Code           | ✅ funcional  |
| 1    | Segurança (permissões + auditoria) + API + UI chat | ✅ funcional  |
| 1.5  | Roteamento automático · histórico · memória (RAG)  | ✅ funcional  |
| 2    | Computer Agent · Voz (STT/TTS + conversa)          | ✅ funcional  |
| 3    | Vision Agent (LLaVA) · Binary Agent (Ghidra)       | ✅ funcional  |
| 4    | Avatar visual no navegador + lip-sync              | ✅ funcional  |
| 5–6  | Avatar **VRM** + sistema de animação em camadas    | ✅ funcional  |
| 7    | Document Agent (ler/criar PDF/Word/Excel/PPT)      | ✅ funcional  |
| 8    | Skills · adaptador MCP                             | ✅ funcional  |
| 9    | **Cognição**: memória cognitiva + grafos + subconsciente | ✅ funcional  |
| 10   | UI command-center (topbar/stage/inspector/settings)| ✅ funcional  |
| 11   | **Projetos**: grafo de código por projeto anexado  | ✅ funcional  |
| 12   | Evolução do Motion Engine do avatar (VRMA, eventos)| 🔜 planejado  |

## Licença

MIT — veja [LICENSE](LICENSE).
