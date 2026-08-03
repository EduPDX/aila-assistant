# Aila Desktop (Electron)

App de desktop que **sobe o backend Python da Aila** e abre a interface do
avatar numa janela — sem precisar abrir o navegador.

## Rodar (desenvolvimento)

Pré-requisitos: o projeto Python instalado na raiz (`pip install -e .`) e
Node.js.

```bash
cd desktop
npm install
npm start
```

O que acontece ao abrir:
1. **git pull** no repositório (atualiza o código se houver novidade — desative
   com a variável `AILA_NO_UPDATE=1`).
2. Sobe o backend Python (`python -m aila.main`) como processo filho.
3. Espera o servidor e abre a janela com a interface (avatar + chat + config).
4. Ao fechar a janela, encerra o backend.

## Gerar o instalador (.exe) — com o Python embutido

Um único comando (na raiz do repo, com o venv ativo):

```powershell
.\desktop\build.ps1
```

Ele faz:
1. **PyInstaller** empacota o backend Python em `dist/aila-backend/aila-backend.exe`.
2. **electron-builder** empacota o app Electron incluindo esse backend
   (`extraResources`) e gera o instalador NSIS em `desktop/dist/`.

No app empacotado, o Electron roda o `aila-backend.exe` (não precisa de
venv/Python instalado). Em dev (`npm start`), ele usa o Python do repositório.

> ⚠ **Primeira vez costuma precisar de ajuste.** Empacotar Python é sensível a
> *hidden imports*. Se o backend não subir, teste-o isolado:
> ```powershell
> .\dist\aila-backend\aila-backend.exe   # deve responder em http://127.0.0.1:8770
> ```
> Erros comuns: módulo faltando → adicione `--hidden-import <nome>` no `build.ps1`.
>
> **STT (microfone) fica fora do .exe** por enquanto (faster-whisper/ctranslate2
> são pesados de empacotar). A **voz de saída (Edge-TTS)** funciona normal.
> Dados graváveis (histórico, memória, VRM escolhido, logs) vão para
> `%LOCALAPPDATA%\Aila`.

## Atualização automática

- **Modo simples (padrão):** a cada abertura o app faz `git pull` — então, tendo
  o repositório clonado, você sempre roda a versão mais nova. É o "atualizar
  direto pelo git".
- **Modo distribuição (futuro):** publicar releases no GitHub e usar
  `electron-updater` (o `publish` já está configurado no `package.json`) para
  baixar/instalar novas versões automaticamente — sem depender de git/venv.
  Requer empacotar o backend Python (ex.: PyInstaller) junto.

## Observações
- O backend precisa do **Ollama** rodando (`ollama serve`) para o chat, e de
  internet para a voz (Edge-TTS).
- Porta padrão: 8770 (`AILA_PORT` para mudar).
