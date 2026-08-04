# Agentes

Cada agente é um módulo especializado que expõe **ferramentas** (tools) para a
IA. As ferramentas seguem o contrato em `aila/tools/schema.py` e passam pelo
controle de permissões antes de executar.

## File Agent — `file` ✅
Manipula arquivos dentro do sandbox.

| Tool | Descrição | Destrutiva |
|------|-----------|:---------:|
| `file.read` | Lê arquivo de texto | — |
| `file.list` | Lista diretório | — |
| `file.search` | Busca por nome/conteúdo | — |
| `file.write` | Cria/sobrescreve arquivo | ✔ (overwrite) |
| `file.move` | Move/renomeia | ✔ (se sobrescreve) |
| `file.delete` | Apaga arquivo/pasta | ✔ |

## Code Agent — `code` ✅
Geração e manutenção de código com modelo especializado (deepseek-coder).

| Tool | Descrição |
|------|-----------|
| `code.generate` | Gera código a partir de uma descrição |
| `code.analyze` | Revisa código e aponta problemas |
| `code.fix` | Corrige código dado um erro |

> Não executa código. Execução chegará via Computer Agent + confirmação.

## Memory Agent — `memory` ✅ (memória de longo prazo / RAG)
Dá à IA controle explícito sobre a memória. Além disso, a engine **recupera e
grava memórias automaticamente** a cada turno (ver abaixo).

| Tool | Descrição |
|------|-----------|
| `memory.save` | Salva um fato/preferência importante para lembrar depois |
| `memory.search` | Busca semântica no que já foi aprendido |

**Como funciona (RAG):** cada memória é um texto + seu *embedding*
(`nomic-embed-text` via Ollama), gravado em `data/memory.db` (SQLite). A busca é
por similaridade de cosseno (numpy). A cada mensagem, a engine:
1. **recupera** as `top_k` memórias mais relevantes (acima de `min_score`) e as
   injeta no contexto como uma nota de sistema;
2. após responder, **grava** a troca (se `store_conversations: true`).

`memory.save` é estado interno da IA — não é bloqueado pelo modo somente-leitura,
apenas auditado. Configuração em `config → memory`. Requer
`ollama pull nomic-embed-text`; se o modelo/embeddings falharem, a memória se
autodesativa sem quebrar o chat.

## Web Agent — `web` ✅ (pesquisa na internet)
Busca na web e leitura de páginas via **DuckDuckGo** (endpoint HTML, sem chave
de API e sem dependência extra — usa o `httpx` já do core). Ações são
**leitura** (funcionam mesmo em modo somente-leitura). Habilitado por padrão.

| Tool | Descrição |
|------|-----------|
| `web.search` | Pesquisa na web → principais resultados (título, link, resumo) |
| `web.fetch` | Baixa uma página (URL http/https) e devolve o texto legível |

Fluxo típico de pesquisa: `web.search` acha as fontes → `web.fetch` lê a mais
relevante → a IA responde com base no conteúdo atual.

## Computer Agent — `computer` ✅ (Fase 2)
Controle do SO. **Habilitado por padrão** com `security.read_only: false` e
`confirm_destructive: true` — a Aila pode atuar, mas cada ação perigosa pede
confirmação. Requer `pip install -e ".[computer]"` para mouse/teclado/janelas
(o `computer.run_command` em PowerShell funciona sem extras).

**Percepção (leitura — permitida mesmo em modo somente-leitura):**

| Tool | Descrição |
|------|-----------|
| `computer.screen_info` | Resolução da tela |
| `computer.list_windows` | Lista títulos das janelas abertas |
| `computer.cursor_position` | Posição atual do mouse |
| `computer.screenshot` | Captura a tela (via `mss`) para o workspace |

**Atuação (escrita — bloqueada em somente-leitura; ✔ = exige confirmação):**

| Tool | Descrição | Confirmação |
|------|-----------|:-----------:|
| `computer.focus_window` | Traz uma janela para frente | — (só read-only) |
| `computer.move_mouse` | Move o cursor para (x,y) | ✔ |
| `computer.click` | Clica (x,y opcional, left/right/middle, duplo) | ✔ |
| `computer.type` | Digita texto | ✔ |
| `computer.hotkey` | Atalho de teclado (ex.: `ctrl+c`) | ✔ |
| `computer.open_app` | Abre um programa | ✔ |
| `computer.run_command` | Executa comando PowerShell | ✔ |

`pyautogui.FAILSAFE` está ligado: leve o mouse ao **canto superior-esquerdo**
para abortar qualquer automação em andamento.

### Segurança
- Vem **ligado** (`read_only: false`), mas `confirm_destructive: true` faz cada
  clique/tecla/comando/abrir-app pedir confirmação na UI (overlay ⚠️).
- Para **travar tudo** de novo (modo somente-leitura), defina
  `security.read_only: true` em `config/local.yaml` ou `AILA_SECURITY__READ_ONLY=true`.
- Toda ação é registrada no log de auditoria (`logs/audit.jsonl`).

## Vision Agent — `vision` ✅ (Fase 3)
Análise visual via modelo multimodal (LLaVA/Qwen-VL) no Ollama. Requer
`ollama pull llava:7b`. Ações são **leitura** (funcionam em modo somente-leitura).

| Tool | Descrição |
|------|-----------|
| `vision.analyze_image` | Descreve/analisa uma imagem do workspace |
| `vision.read_text` | Lê/extrai o texto visível numa imagem (OCR via modelo) |
| `vision.screenshot_analyze` | Captura a tela (mss) e interpreta a interface |

Envie imagens pela UI (botão 📎) ou via `POST /api/upload` → elas vão para
`workspace/uploads/`. O Vision Agent lê imagens do workspace, então também
analisa screenshots do Computer Agent (loop **ver → entender → agir**).
Se o modelo não estiver baixado, as tools retornam instrução para `ollama pull`.

## Binary Agent — `binary` ✅ (Fase 3)
Triagem de binários (sem dependências) + descompilação com Ghidra. Todas as
ações são **leitura**. Detalhes em [BINARY.md](BINARY.md).

| Tool | Descrição |
|------|-----------|
| `binary.identify` | Tipo pelo cabeçalho (magic bytes) + tamanho |
| `binary.strings` | Extrai strings ASCII legíveis |
| `binary.entropy` | Entropia de Shannon (detecta packed/cifrado) |
| `binary.pe_info` | Cabeçalho PE (arquitetura, formato, seções) |
| `binary.decompile` | Ghidra headless → pseudo-C (requer `binary.ghidra_path`) |

Análise **estática** — o binário nunca é executado. A decompilação usa
`analyzeHeadless` + um script Jython em `aila/tools/ghidra/`.

## Como a IA escolhe a ferramenta (roteamento automático)

Por padrão (modo **Auto**), a engine envia os JSON Schemas de todas as tools ao
modelo em **streaming**. A própria IA decide se responde direto (conversa) ou se
emite `tool_calls`. Quando emite, a engine executa cada chamada pelo
`ToolRegistry` — respeitando permissões — realimenta o resultado e deixa o
modelo sintetizar a resposta final, que volta em streaming. O usuário pode forçar
o modo **Chat** (sem ferramentas) para menor latência. Ver
[ARCHITECTURE.md](ARCHITECTURE.md).
