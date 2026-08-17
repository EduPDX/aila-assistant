# ============================================================
#  Aila - rodar do CODIGO-FONTE (dev). SEM build.
#   - sobe o backend Python (FastAPI/uvicorn) do repositorio;
#   - escolhe uma porta LIVRE automaticamente (evita 8770 reservada/ocupada);
#   - abre a Aila no navegador assim que o servidor responder;
#   - reload automatico: editou um .py de aila/ -> reinicia sozinho.
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

# Acha uma porta que o Windows PERMITA bindar (WinError 10013 = porta reservada,
# ex.: faixas do Hyper-V/WSL; ou ja em uso pelo .exe). Testa candidatas.
function Find-Port($cands) {
  foreach ($p in $cands) {
    try {
      $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, [int]$p)
      $l.Start(); $l.Stop()
      return $p
    } catch { }
  }
  return $cands[0]
}

if ($env:AILA_PORT) { $port = $env:AILA_PORT }
else { $port = Find-Port @(8770, 8801, 8877, 8181, 8123, 9770, 8912) }
$env:AILA_PORT = "$port"                 # o backend BINDA nesta porta
$url = "http://127.0.0.1:$port/"
if (-not $NoReload) { $env:AILA_RELOAD = "1" }

# abre o navegador quando o servidor responder (processo paralelo, oculto)
$opener = "for(`$i=0;`$i -lt 90;`$i++){try{Invoke-WebRequest '$url' -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process '$url'; break}catch{Start-Sleep 1}}"
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", $opener | Out-Null

Write-Host "============================================================" -ForegroundColor Green
Write-Host " Aila (codigo-fonte)  ->  $url" -ForegroundColor Green
if (-not $NoReload) { Write-Host " Reload ON: editou um .py? o backend reinicia sozinho." -ForegroundColor Green }
Write-Host " Front (JS/CSS): recarregue o navegador (Ctrl+R)." -ForegroundColor DarkGray
Write-Host " Encerrar: Ctrl+C nesta janela." -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Green

& $py -m aila.main
