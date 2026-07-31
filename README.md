# Aila — Assistente de IA Local Multimodal para Windows

> Um agente de IA multimodal, com voz e avatar 3D, que roda **100% local** no seu PC.
> Capacidades no estilo ChatGPT + Claude Code, sem depender de nuvem.

[![Status](https://img.shields.io/badge/status-alpha-orange)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2011-informational)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## O que é

**Aila** é uma assistente de IA local, modular e escalável. Ela conversa, mantém
contexto, executa tarefas no seu computador, analisa imagens e código, fala por voz
e (na fase final) é representada por um avatar 3D com emoções e sincronização labial.

Tudo roda na sua máquina usando modelos abertos (**Llama, Qwen, DeepSeek Coder,
Mistral**) via **Ollama** e **llama.cpp**.

## Hardware alvo

| Componente | Especificação        | Observação                                       |
|------------|----------------------|--------------------------------------------------|
| CPU        | AMD Ryzen 5 5500     | 6 núcleos / 12 threads                            |
| GPU        | NVIDIA RTX 4060 8GB  | Aceleração **CUDA** (llama.cpp/Ollama offload)    |
| RAM        | 32 GB                | Confortável para modelos 7B–14B quantizados       |

> Com 8 GB de VRAM, o ponto ideal são modelos **7B–8B quantizados (Q4_K_M)**, que
> rodam inteiramente na GPU. Modelos 14B rodam em modo híbrido GPU+CPU.
> Veja recomendações em [`config/models.yaml`](config/models.yaml).

## Arquitetura (visão rápida)

```
┌──────────────────────────────────────────────────────────────┐
│                         UI (Web / Desktop)                     │
│           chat · voz · painel de tarefas · status              │
└───────────────────────────┬──────────────────────────────────┘
                            │ WebSocket / REST
┌───────────────────────────▼──────────────────────────────────┐
│                        AILA CORE ENGINE                        │
│   orquestrador · contexto · roteador de agentes · tools        │
└───┬───────────┬───────────┬───────────┬───────────┬───────────┘
    │           │           │           │           │
┌───▼───┐  ┌────▼────┐  ┌───▼────┐  ┌───▼────┐  ┌───▼──────┐
│  LLM  │  │ Agents  │  │ Voice  │  │ Vision │  │  Avatar  │
│Ollama │  │ file    │  │ STT/TTS│  │ LLaVA  │  │ emotion  │
│llama  │  │ code    │  │Whisper │  │ Qwen-V │  │ protocol │
│.cpp   │  │ computer│  │Piper   │  │        │  │          │
│       │  │ vision  │  │XTTS    │  │        │  │          │
│       │  │ binary  │  │        │  │        │  │          │
└───────┘  └─────────┘  └────────┘  └────────┘  └──────────┘
        todos os módulos se comunicam pelo EVENT BUS interno
```

Detalhes completos em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Estrutura do projeto

```
aila-assistant/
├── aila/                 # Backend Python (pacote principal)
│   ├── core/             # Engine, event bus, config, contexto
│   ├── llm/              # Backends de modelos (Ollama, llama.cpp)
│   ├── agents/           # File, Code, Computer, Vision, Binary
│   ├── tools/            # Registro de ferramentas chamáveis pela IA
│   ├── security/         # Permissões, sandbox, auditoria
│   ├── voice/            # STT (Whisper) e TTS (Piper/XTTS)
│   ├── vision/           # Análise de imagem / screenshots
│   ├── avatar/           # Emotion engine + protocolo do avatar 3D
│   ├── database/         # Persistência (SQLite)
│   └── api/              # Rotas REST + WebSocket
├── ui/                   # Interface web inicial
├── config/               # Configuração YAML
├── docs/                 # Documentação de arquitetura
├── scripts/              # Setup e download de modelos (PowerShell)
└── models/               # (gitignored) pesos GGUF locais
```

## Início rápido

### 1. Pré-requisitos

- Windows 11, Python 3.11+ (testado em 3.14)
- [Ollama](https://ollama.com/download) instalado
- Drivers NVIDIA + CUDA atualizados

### 2. Instalação

```powershell
cd aila-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
copy .env.example .env
```

### 3. Baixar um modelo

```powershell
ollama serve        # em um terminal
.\scripts\pull_models.ps1
```

### 4. Rodar

```powershell
python -m aila.main
```

Abra `http://localhost:8770` no navegador.

## Roadmap

O projeto é entregue em fases. O que já funciona e o que vem a seguir está em
[`docs/ROADMAP.md`](docs/ROADMAP.md).

| Fase | Módulo                              | Status        |
|------|-------------------------------------|---------------|
| 1    | Core engine + event bus + config    | ✅ funcional  |
| 1    | LLM backend (Ollama)                | ✅ funcional  |
| 1    | Sistema de agentes + File/Code      | ✅ funcional  |
| 1    | Segurança (permissões + auditoria)  | ✅ funcional  |
| 1    | API REST/WebSocket + UI de chat     | ✅ funcional  |
| 2    | Computer Agent (PyAutoGUI/WinAPI)   | 🚧 interface  |
| 2    | Voice (Whisper + Piper)             | 🚧 interface  |
| 3    | Vision (LLaVA/Qwen-VL)              | 🚧 interface  |
| 3    | Binary Agent (Ghidra)               | 🚧 interface  |
| 4    | Avatar 3D (Unreal/Unity)            | 🧩 protocolo  |

## Segurança

A Aila pode controlar o seu computador. Por isso, **toda ação destrutiva exige
confirmação**, há **modo somente-leitura**, **sandbox de caminhos** e **log de
auditoria** de tudo. Leia [`docs/SECURITY.md`](docs/SECURITY.md) antes de habilitar
o Computer Agent.

## Licença

MIT — veja [LICENSE](LICENSE).
