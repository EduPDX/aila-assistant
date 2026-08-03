# ============================================================
#  Build do app desktop Aila (.exe)
#  1) empacota o backend Python com PyInstaller
#  2) empacota o app Electron (electron-builder) incluindo o backend
#
#  Uso (na raiz do repo, com o venv ativo):
#     .\desktop\build.ps1
#
#  ⚠ Primeira vez costuma exigir ajustes (hidden-imports faltando etc.).
#     Rode o backend empacotado sozinho para depurar:
#     .\dist\aila-backend\aila-backend.exe  (deve subir em http://127.0.0.1:8770)
# ============================================================
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Write-Host "== 1/2  Empacotando o backend Python (PyInstaller) ==" -ForegroundColor Cyan
& $py -m pip install --quiet pyinstaller

# Nota: STT (faster-whisper/ctranslate2/av) fica FORA do bundle para viabilizar
# o build. A entrada por microfone fica indisponível no .exe (voz de saída via
# Edge-TTS funciona). Para incluir STT, remova os --exclude-module e ajuste.
& $py -m PyInstaller --noconfirm --clean --name aila-backend --onedir --console `
    --distpath (Join-Path $root "dist") `
    --workpath (Join-Path $root "build") `
    --specpath (Join-Path $root "build") `
    --add-data "$($root)\config;config" `
    --add-data "$($root)\ui;ui" `
    --collect-all uvicorn `
    --collect-all edge_tts `
    --collect-all aiohttp `
    --collect-submodules aila `
    --hidden-import aila.main `
    --exclude-module faster_whisper `
    --exclude-module ctranslate2 `
    --exclude-module av `
    --exclude-module torch `
    (Join-Path $root "desktop\backend\aila_backend.py")

Write-Host "== 2/2  Empacotando o app Electron ==" -ForegroundColor Cyan
Set-Location (Join-Path $root "desktop")
if (-not (Test-Path "node_modules")) { npm install }
npm run dist

Write-Host ""
Write-Host "Pronto! Instalador em desktop\dist\" -ForegroundColor Green
