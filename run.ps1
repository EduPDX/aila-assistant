# ============================================================
#  Aila - rodar do CODIGO-FONTE (dev). SEM build.
#   - sobe o backend Python (FastAPI/uvicorn) do repositorio;
#   - escolhe uma porta LIVRE automaticamente (evita 8770 reservada/ocupada);
#   - abre a Aila numa JANELA DEDICADA (Chrome/Edge em modo -app, perfil proprio),
#     como um app -> sem abas, sem barra de endereco, isolada do seu navegador;
#   - reload automatico: editou um .py de aila/ -> reinicia sozinho.
#
#  Uso: duplo-clique em run.bat  (ou  .\run.ps1)
#       .\run.ps1 -Tab   -> abre no navegador padrao (aba comum), nao na janela.
#  Encerrar: Ctrl+C nesta janela.
# ============================================================
param([switch]$NoReload, [switch]$Tab)

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

# Acha um navegador Chromium (Chrome ou Edge) p/ abrir em MODO APP (janela
# dedicada). Edge existe em todo Windows 11, entao quase sempre acha.
function Find-Browser {
  $cands = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
  )
  foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return $c } }
  return $null
}

$browser = Find-Browser
$profileDir = Join-Path $root ".aila-window"   # perfil PROPRIO da Aila (isolado)

# monta o comando de abertura (janela dedicada -app, ou aba comum com -Tab)
if ($browser -and -not $Tab) {
  $mode = "janela dedicada ($([System.IO.Path]::GetFileNameWithoutExtension($browser)))"
  $launch = "Start-Process '$browser' -ArgumentList '--app=$url','--user-data-dir=$profileDir','--no-first-run','--no-default-browser-check','--window-size=1280,860'"
} else {
  $mode = "navegador padrao"
  $launch = "Start-Process '$url'"
}

# abre quando o servidor responder (processo paralelo, oculto)
$opener = "for(`$i=0;`$i -lt 90;`$i++){try{Invoke-WebRequest '$url' -UseBasicParsing -TimeoutSec 2 | Out-Null; $launch; break}catch{Start-Sleep 1}}"
Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", $opener | Out-Null

Write-Host "============================================================" -ForegroundColor Green
Write-Host " Aila (codigo-fonte)  ->  $url" -ForegroundColor Green
Write-Host " Abrindo em: $mode" -ForegroundColor Green
if (-not $NoReload) { Write-Host " Reload ON: editou um .py? o backend reinicia sozinho." -ForegroundColor Green }
Write-Host " Front (JS/CSS): recarregue a janela (Ctrl+R)." -ForegroundColor DarkGray
Write-Host " Comum (aba): .\run.ps1 -Tab    Encerrar: Ctrl+C aqui." -ForegroundColor DarkGray
Write-Host "============================================================" -ForegroundColor Green

& $py -m aila.main
