# ============================================================
#  Build + Deploy do app desktop Aila (.exe) — UM COMANDO.
#    1) empacota o backend Python (PyInstaller)
#    2) empacota o app Electron (electron-builder, instalador NSIS)
#    3) COPIA o instalador para a pasta Downloads
#
#  Uso (na raiz do repo):
#     .\desktop\build.ps1
#     (ou duplo-clique em build.bat na raiz)
#
#  Opcional:
#     .\desktop\build.ps1 -Pull   # git pull antes de buildar
# ============================================================
param([switch]$Pull)

$ErrorActionPreference = "Stop"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

function Step($n, $msg) { Write-Host "`n== $n  $msg ==" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "`nFALHOU: $msg" -ForegroundColor Red; exit 1 }
# roda um comando nativo e aborta se o exit code != 0. NÃO usar $args como nome
# de parâmetro: é variável automática do PowerShell e quebra o splatting (@arglist).
function Native($file, $arglist) {
  & $file @arglist
  if ($LASTEXITCODE -ne 0) { Fail "$file (exit $LASTEXITCODE)" }
}

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

if ($Pull) { Step "0/3" "git pull"; Native "git" @("pull") }

Step "1/3" "Empacotando o backend Python (PyInstaller)"
Native $py @("-m", "pip", "install", "--quiet", "pyinstaller")
# Code Graph PRÉ-CONSTRUÍDO (o .exe não tem as fontes .py p/ varrer → embute pronto)
Remove-Item (Join-Path $root "code_graph.prebuilt.db*") -ErrorAction SilentlyContinue
Native $py @((Join-Path $root "desktop\prebuild_graph.py"))
# STT (faster-whisper/ctranslate2/av/torch) fica FORA do bundle p/ viabilizar o
# build; a voz de SAÍDA (Edge-TTS) funciona sem eles (serve MP3 direto).
Native $py @(
  "-m", "PyInstaller", "--noconfirm", "--clean", "--name", "aila-backend", "--onedir", "--console",
  "--distpath", (Join-Path $root "dist"),
  "--workpath", (Join-Path $root "build"),
  "--specpath", (Join-Path $root "build"),
  "--add-data", "$($root)\config;config",
  "--add-data", "$($root)\ui;ui",
  "--add-data", "$($root)\code_graph.prebuilt.db;.",   # grafo de código pré-construído
  "--collect-all", "uvicorn",
  "--collect-all", "edge_tts",
  "--collect-all", "aiohttp",
  "--collect-submodules", "aila",
  "--hidden-import", "aila.main",
  "--exclude-module", "faster_whisper",
  "--exclude-module", "ctranslate2",
  "--exclude-module", "av",
  "--exclude-module", "torch",
  (Join-Path $root "desktop\backend\aila_backend.py")
)
if (-not (Test-Path (Join-Path $root "dist\aila-backend\aila-backend.exe"))) {
  Fail "backend não foi gerado (dist\aila-backend\aila-backend.exe)"
}

Step "2/3" "Empacotando o app Electron (electron-builder)"
Set-Location (Join-Path $root "desktop")
if (-not (Test-Path "node_modules")) { Native "npm" @("install") }
Native "npm" @("run", "dist")

Step "3/3" "Copiando o instalador para Downloads"
$installer = Get-ChildItem (Join-Path $root "desktop\dist") -Filter "Aila Setup *.exe" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) { Fail "instalador não encontrado em desktop\dist\" }
$downloads = Join-Path $env:USERPROFILE "Downloads"
$dest = Join-Path $downloads $installer.Name
try {
  Copy-Item $installer.FullName $dest -Force
} catch {
  Fail "não consegui copiar p/ Downloads (feche o Aila/instalador se estiver aberto). $_"
}

$sw.Stop()
$mb = [math]::Round($installer.Length / 1MB, 1)
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " PRONTO em $([math]::Round($sw.Elapsed.TotalMinutes,1)) min  ·  $mb MB" -ForegroundColor Green
Write-Host " Instalador: $dest" -ForegroundColor Green
Write-Host " (feche o Aila aberto antes de reinstalar por cima)" -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Green
