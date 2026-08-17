# ============================================================
#  Aila — rodar do CÓDIGO-FONTE (dev). SEM build.
#   - sobe o backend Python (FastAPI/uvicorn) do repositório;
#   - abre a Aila no navegador assim que o servidor responder;
#   - reload automático: editou um .py de aila/ → reinicia sozinho
#     (a própria Aila se auto-modificando aparece na hora).
#
#  Uso: duplo-clique em run.bat  (ou  .\run.ps1)
#  Encerrar: Ctrl+C nesta janela.
# ============================================================
param([switch]$NoReload)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$port = if ($env:AILA_PORT) { $env:AILA_PORT } else { "8770" }
$url  = "http://127.0.0.1:$port/"
if (-not $NoReload) { $env:AILA_RELOAD = "1" }

# abre o navegador quando o servidor responder (processo paralelo, oculto)
$opener = "for(`$i=0;`$i -lt 90;`$i++){try{Invoke-WebRequest '$url' -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process '$url'; break}catch{Start-Sleep 1}}"
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", $opener | Out-Null

Write-Host "============================================================" -ForegroundColor Green
Write-Host " Aila (código-fonte) → $url" -ForegroundColor Green
if (-not $NoReload) { Write-Host " Reload ON: editou um .py? o backend reinicia sozinho." -ForegroundColor Green }
Write-Host " Front (JS/CSS): recarregue o navegador (Ctrl+R)." -ForegroundColor DarkGray
Write-Host " Encerrar: Ctrl+C nesta janela." -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Green

& $py -m aila.main
