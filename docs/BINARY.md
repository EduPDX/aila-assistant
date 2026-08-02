# Binary Agent

Análise de arquivos binários — da triagem rápida à descompilação com Ghidra.
Todas as operações são **leitura** (funcionam em modo somente-leitura).

## Triagem (sem dependências)

Funciona só com a biblioteca padrão do Python, sem instalar nada:

| Tool | O que faz |
|------|-----------|
| `binary.identify` | Tipo do arquivo pelos *magic bytes* (PE, ELF, ZIP, PDF, …) + tamanho |
| `binary.strings` | Extrai strings ASCII legíveis |
| `binary.entropy` | Entropia de Shannon (0–8). **>7,5 ≈ comprimido/cifrado/packed** |
| `binary.pe_info` | Cabeçalho PE de executáveis Windows: arquitetura, formato, seções |

Exemplo (sobre `notepad.exe`):

```
Tipo: Executável Windows (PE/DOS)  ·  360.448 bytes
Formato: PE32+ (64-bit)  ·  Arquitetura: x64 (AMD64)
Seções (8): .text .rdata .data .pdata .didat .rsrc .reloc ...
Entropia: 6.483 / 8.0 — normal para código/dados
```

## Descompilação com Ghidra

| Tool | O que faz |
|------|-----------|
| `binary.decompile` | Roda o **Ghidra headless** e devolve pseudo-C das funções |

### Configuração

1. Baixe o [Ghidra](https://ghidra-sre.org/) e descompacte.
2. Aponte a config para a pasta que contém `support/analyzeHeadless`:

```yaml
# config/local.yaml  (ou variável AILA_BINARY__GHIDRA_PATH)
binary:
  ghidra_path: "C:/ferramentas/ghidra_11.x"
  analysis_timeout: 600
```

Sem isso, `binary.decompile` retorna uma mensagem explicando como configurar —
a triagem acima continua funcionando normalmente.

### Como funciona

A Aila invoca `analyzeHeadless` num projeto temporário, importando o binário e
rodando um script Jython (`aila/tools/ghidra/decompile_headless.py`) que usa a
`DecompInterface` do Ghidra para descompilar as primeiras funções (ou uma função
específica, se você indicar `function`). A saída é capturada entre marcadores e
devolvida à conversa.

> Ghidra é pesado e lento; a primeira análise de um binário grande pode levar
> minutos. Ajuste `analysis_timeout` conforme necessário.

## Segurança

- É análise **estática** — o binário **não é executado**.
- Fica confinada ao workspace (sandbox), como os demais agentes.
- Ainda assim, analise apenas arquivos de origem confiável.
