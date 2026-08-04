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
