# Visão (Vision Agent)

A Aila **enxerga**: analisa imagens, lê texto (OCR) e interpreta a tela, usando
um modelo multimodal local (LLaVA / Qwen-VL) servido pelo Ollama.

```
imagem (upload 📎 ou screenshot) → base64 → Ollama (llava:7b) → descrição/OCR
```

## Pré-requisitos

```bash
ollama pull llava:7b        # ~4.7 GB  (ou qwen2.5vl:7b)
pip install -e ".[vision]"  # captura de tela (mss)
```

O modelo de visão é definido em `config → llm.vision_model` (padrão `llava:7b`).
Se o modelo não estiver baixado, as ferramentas retornam a instrução de `pull`.

## Ferramentas

| Tool | Descrição |
|------|-----------|
| `vision.analyze_image` | Descreve/analisa uma imagem do workspace |
| `vision.read_text` | Extrai o texto visível (OCR via modelo) |
| `vision.screenshot_analyze` | Captura a tela agora e interpreta a interface |

Todas são **operações de leitura** — funcionam mesmo com `security.read_only: true`.

## Como usar

- **Na UI**: clique em 📎, escolha uma imagem — ela é enviada para
  `workspace/uploads/` e a Aila a analisa automaticamente (modo Auto).
- **Por voz/texto**: "tire um print e me diga o que está na tela" → a IA chama
  `vision.screenshot_analyze`.
- **Via API**: `POST /api/upload` (multipart `file`) salva no workspace e
  retorna o caminho relativo.

## O ciclo ver → entender → agir

Como o Vision Agent lê imagens do workspace e o Computer Agent salva screenshots
lá, os dois se combinam:

1. `computer.screenshot` (ou `vision.screenshot_analyze`) captura a tela.
2. `vision.*` interpreta o que há nela.
3. A IA decide e o Computer Agent atua (`computer.click`, `computer.type`, …),
   sempre com permissão/confirmação.

## Modelos

Veja [`config/models.yaml`](../config/models.yaml):
- `llava:7b` (~6 GB VRAM) — recomendado, cabe na RTX 4060.
- `qwen2.5vl:7b` — forte em interpretação de UI / OCR.

## Roadmap
- [ ] Retornar **coordenadas** de elementos (clicar exatamente onde a visão apontou)
- [ ] Downscale automático de imagens grandes
- [ ] Visão contínua (analisar a tela em intervalos) para automação assistida
