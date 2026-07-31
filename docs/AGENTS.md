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

## Computer Agent — `computer` ✅ (Fase 2)
Controle do SO. **Desabilitado por padrão** (segurança). Requer
`pip install -e ".[computer]"` e habilitar em `config → agents.enabled: [..., computer]`.

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

### Como habilitar (com segurança)
1. `pip install -e ".[computer]"`
2. Em `config/local.yaml` (ou `.env`), adicione `computer` a `agents.enabled`.
3. Deixe `security.read_only: false` **apenas** quando quiser que ela atue.
4. Mantenha `security.confirm_destructive: true` — cada clique/tecla/comando
   pede sua confirmação na UI.

## Vision Agent — `vision` 🚧 (Fase 3)
Análise visual via modelo multimodal (LLaVA/Qwen-VL) no Ollama.

| Tool | Descrição |
|------|-----------|
| `vision.analyze_image` | Descreve/analisa uma imagem do workspace |
| `vision.screenshot_analyze` | Captura a tela e interpreta (extra `vision`) |

## Binary Agent — `binary` 🚧 (Fase 3)
Triagem de binários e ponte para o Ghidra.

| Tool | Descrição |
|------|-----------|
| `binary.identify` | Identifica o tipo pelo cabeçalho (magic bytes) |
| `binary.strings` | Extrai strings ASCII legíveis |

Integração Ghidra headless (descompilação) planejada para a Fase 3.

## Como a IA escolhe a ferramenta (roteamento automático)

Por padrão (modo **Auto**), a engine envia os JSON Schemas de todas as tools ao
modelo em **streaming**. A própria IA decide se responde direto (conversa) ou se
emite `tool_calls`. Quando emite, a engine executa cada chamada pelo
`ToolRegistry` — respeitando permissões — realimenta o resultado e deixa o
modelo sintetizar a resposta final, que volta em streaming. O usuário pode forçar
o modo **Chat** (sem ferramentas) para menor latência. Ver
[ARCHITECTURE.md](ARCHITECTURE.md).
