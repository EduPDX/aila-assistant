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

## Gerar o instalador (.exe)

```bash
npm run dist
```

Usa `electron-builder` (config no `package.json`). Gera um instalador NSIS em
`desktop/dist/`.

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
