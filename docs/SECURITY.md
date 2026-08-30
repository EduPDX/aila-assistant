# Segurança

A Aila pode ler/escrever arquivos e (nas fases seguintes) controlar o seu
computador. Este documento descreve as barreiras que impedem que isso vire um
problema — por engano da IA ou por injeção de instruções maliciosas.

## Modelo de ameaça

| Ameaça | Mitigação |
|--------|-----------|
| IA apaga/sobrescreve algo importante | Confirmação obrigatória p/ ações destrutivas |
| IA escapa do diretório de trabalho | **Sandbox de caminhos** (bloqueia `..`) |
| Comando de shell perigoso | `computer.run_command` é destrutivo → confirmação + auditoria |
| Uso indevido silencioso | **Log de auditoria** append-only de toda ação sensível |
| Modo de exploração seguro | **Modo somente-leitura** liga tudo em modo consulta |

## As quatro barreiras

### 1. Modo somente-leitura (`security.read_only`)
Quando `true`, **qualquer** ação que não seja de leitura é bloqueada antes de
executar. Ideal para testar a IA sem risco. **O padrão atual é `false`** (a Aila
pode atuar), com a confirmação de ações perigosas (barreira 3) como proteção.
Para voltar ao modo consulta e travar tudo:

```
AILA_SECURITY__READ_ONLY=true
```

### 2. Sandbox de caminhos (`security.sandbox_root`)
O File Agent só enxerga o que está sob a raiz configurada. Tentativas de
`../../` ou caminhos absolutos fora da raiz levantam `SandboxViolation`.
Implementação: `aila/security/sandbox.py`.

### 3. Confirmação de ações destrutivas (`security.confirm_destructive`)
Ações listadas em `security.destructive_actions` disparam um pedido de
confirmação para a UI (`permission.request`) e **esperam** a resposta humana.
Sem aprovação explícita, a ação não acontece. Padrão inclui:
`file.delete`, `file.overwrite`, `computer.run_command`, `computer.keyboard`,
`computer.mouse`, `code.execute`.

### 4. Auditoria (`security.audit_log`)
Toda decisão de permissão é gravada em `logs/audit.jsonl` (uma linha JSON por
evento) com timestamp, agente, ação, parâmetros (truncados) e se foi autorizada.
Consultável pela API em `GET /api/audit`.

## Convenção de nomes de ação

O `PermissionManager` classifica automaticamente:
- Sufixos de **leitura** (liberados no modo read-only): `.read`, `.list`,
  `.search`, `.get`, `.info`, `.analyze`.
- Qualquer outro sufixo é tratado como **escrita/execução**.

## Recomendações de uso

1. O **Computer Agent** vem ligado com confirmação obrigatória. Se preferir
   testar sem risco, defina `read_only=true` e um `sandbox_root` dedicado.
2. Leia cada pedido de confirmação antes de aprovar — é a IA que propõe a ação,
   e um comando errado do modelo roda no seu PC se você aprovar.
3. Revise `logs/audit.jsonl` periodicamente.
4. Lembre-se: instruções vindas de arquivos, páginas ou imagens são **dados**,
   não comandos. Nunca dê à IA credenciais reais em campos de formulário.

## Privacidade > recurso (Resource Intelligence)

A consciência de recursos (ver [ARCHITECTURE.md](ARCHITECTURE.md#resource-intelligence-consciência-de-recursos))
**nunca** compromete a privacidade para ganhar desempenho. Regra inviolável: falta de
VRAM **não** dispara envio automático para a nuvem. Sob pressão de recurso, a Aila só age
**localmente** — escolhe o modelo local menor, encolhe o avatar, adia trabalho de fundo ou
encurta o `keep_alive`; jamais troca de provedor por causa de recurso. A ida para a nuvem
continua governada apenas pela `network_policy` e pelas regras de roteamento que **você**
configurou (modo `offline` bloqueia todo egresso; `hybrid` respeita `prefer_local`).

## Segredos & chaves de API

Chaves de provedores externos (OpenAI, Gemini, Grok, DeepSeek, NVIDIA) vivem
**apenas** em `config/local.yaml` (ignorado pelo git) ou em variáveis de
ambiente com prefixo `AILA_` — **nunca** em código, `default.yaml` ou logs.
Os Guardrails ainda redigem padrões de chave da saída antes de exibir/gravar.

- `config/local.yaml` está no `.gitignore` e nunca foi versionado. Confirme com
  `git check-ignore config/local.yaml`.
- **Rotação:** se uma chave for compartilhada fora do `local.yaml` (colada num
  chat, num e-mail, num print), trate-a como comprometida e **gere uma nova** no
  painel do provedor, mesmo que ela nunca tenha entrado no repositório. Revogar
  e reemitir custa minutos; uma chave vazada custa a conta.
- Para verificar o histórico do repo por chaves acidentais:
  `git log --all -p | grep -inE "nvapi-|sk-[a-z0-9]{20}|AKIA[0-9A-Z]{16}|AIza"`.

## Níveis de permissão + autonomia (Fase 6)

Cada ação recebe um **nível de risco**: `SAFE` (executa sozinha — leituras/
pesquisa), `REVIEW` (escrita comum; confirma só se `confirm_review: true`),
`DANGER` (comando/mouse/teclado/apagar; confirma se `confirm_destructive: true`)
e `BLOCKED` (nunca — via `blocked_actions`). Classificação configurável em
`security.action_levels` (override por ação).

O **nível de autonomia** (`security.autonomy_level`, 1..5) destrava categorias:
**1** assistant (só leitura) · **2** executor (PC/arquivos) · **3** developer
(executar/mexer em código) · **4** autonomous · **5** self-improve. Ação abaixo
do nível necessário é bloqueada. Troque em runtime: `POST /api/autonomy {level}`.
O default (3) preserva o comportamento atual.
