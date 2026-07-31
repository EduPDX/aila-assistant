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

## Computer Agent — `computer` 🚧 (Fase 2)
Controle do SO. **Desabilitado por padrão.** Requer `pip install -e ".[computer]"`.

| Tool | Descrição | Destrutiva |
|------|-----------|:---------:|
| `computer.run_command` | Executa comando PowerShell | ✔ |
| `computer.open_app` | Abre um programa | ✔ |
| `computer.type` | Digita via teclado virtual | ✔ |

`pyautogui.FAILSAFE` está ligado: leve o mouse ao canto superior-esquerdo para
abortar qualquer automação.

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

## Como a IA escolhe a ferramenta

No **modo agente**, a engine envia os JSON Schemas de todas as tools ao modelo
(`chat_message(tools=...)`). O modelo responde com `tool_calls`; a engine
executa cada uma pelo `ToolRegistry`, respeitando permissões, e realimenta o
resultado até o modelo produzir a resposta final. Ver [ARCHITECTURE.md](ARCHITECTURE.md).
