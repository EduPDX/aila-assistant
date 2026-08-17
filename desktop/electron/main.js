// ============================================================================
//  Aila Desktop (Electron) — casco que:
//   1. (opcional) atualiza o código pelo git (git pull)
//   2. sobe o backend Python da Aila (uvicorn/FastAPI) como processo filho
//   3. abre uma janela com a interface do avatar (localhost)
//   4. encerra o backend ao fechar
// ============================================================================
const { app, BrowserWindow, dialog } = require('electron');
const { spawn, execFile } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

// App LOCAL (localhost): nunca cachear a UI → após um update, os módulos ES/CSS
// novos carregam na hora (sem servir versão antiga do cache do Chromium).
app.commandLine.appendSwitch('disable-http-cache');

const REPO_ROOT = path.resolve(__dirname, '..', '..'); // desktop/electron -> repo
const PORT = process.env.AILA_PORT || 8770;
const URL = `http://127.0.0.1:${PORT}/`;
// git pull só faz sentido no modo dev (rodando do repositório); no .exe
// empacotado a atualização é via electron-updater (futuro).
const GIT_UPDATE = !app.isPackaged && process.env.AILA_NO_UPDATE !== '1';

// caminho do backend empacotado (dentro dos resources do app)
function bundledBackend() {
  return path.join(process.resourcesPath, 'aila-backend', 'aila-backend.exe');
}

let backend = null;
let win = null;

function pythonExe() {
  const venv = path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe');
  return fs.existsSync(venv) ? venv : 'python';
}

// --------- 1. auto-update pelo git (pull) ---------
function gitPull() {
  return new Promise((resolve) => {
    if (!GIT_UPDATE || !fs.existsSync(path.join(REPO_ROOT, '.git'))) return resolve('sem git');
    execFile('git', ['pull', '--ff-only'], { cwd: REPO_ROOT, timeout: 20000 }, (err, stdout) => {
      if (err) return resolve('git pull falhou (seguindo mesmo assim)');
      resolve(stdout.includes('Already up to date') ? 'já atualizado' : 'atualizado ✓');
    });
  });
}

// --------- 2. sobe o backend Python ---------
function startBackend() {
  const env = { ...process.env, AILA_PORT: String(PORT) };
  if (app.isPackaged && fs.existsSync(bundledBackend())) {
    // empacotado: usa o backend .exe (PyInstaller)
    backend = spawn(bundledBackend(), [], { env, stdio: 'ignore' });
  } else {
    // dev: usa o Python do repositório (venv)
    backend = spawn(pythonExe(), ['-m', 'aila.main'], { cwd: REPO_ROOT, env, stdio: 'ignore' });
  }
  backend.on('error', (e) => {
    dialog.showErrorBox('Aila', 'Não consegui iniciar o backend:\n' + e.message +
      (app.isPackaged ? '' : '\n\nEm dev, rode antes:  pip install -e .'));
  });
}

// --------- 3. espera o servidor responder ---------
function waitForServer(timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    (function ping() {
      http.get(URL + 'api/status', (res) => { res.destroy(); resolve(); })
        .on('error', () => {
          if (Date.now() - start > timeoutMs) return reject(new Error('timeout'));
          setTimeout(ping, 500);
        });
    })();
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1200, height: 800, minWidth: 900, minHeight: 620,
    backgroundColor: '#0a0e14', title: 'Aila',
    webPreferences: { contextIsolation: true, preload: path.join(__dirname, 'preload.js') },
  });
  win.removeMenu();
  // limpa qualquer cache antigo (de uma versão instalada antes) antes de carregar
  win.webContents.session.clearCache().catch(() => {}).finally(() => win.loadURL(URL));
  win.on('closed', () => { win = null; });
}

app.whenReady().then(async () => {
  await gitPull();
  startBackend();
  try {
    await waitForServer();
    createWindow();
  } catch (e) {
    dialog.showErrorBox('Aila', 'O backend não respondeu a tempo. Verifique o Python/Ollama.');
    app.quit();
  }
});

function stopBackend() { if (backend && !backend.killed) { try { backend.kill(); } catch (e) {} } }
app.on('window-all-closed', () => { stopBackend(); app.quit(); });
app.on('before-quit', stopBackend);
process.on('exit', stopBackend);
