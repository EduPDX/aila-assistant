<#
.SYNOPSIS
    Instalador de um comando da Aila.

.EXAMPLE
    .\install.ps1                       # base + venv + .env
    .\install.ps1 -Extras voice,vision  # com STT e captura de tela
    .\install.ps1 -All -PullModels      # tudo + baixa os modelos do Ollama

.NOTES
    Extras disponíveis: computer, voice, piper, vision, dev
#>
param(
    [string[]] $Extras = @(),
    [switch]   $All,
    [switch]   $PullModels
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  Aila - instalador" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# 1. Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "Python 3.11+ nao encontrado no PATH." -ForegroundColor Red; exit 1 }
Write-Host "Python: $((python --version) 2>&1)" -ForegroundColor Green

# 2. venv
if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}
$vpy = Join-Path $root ".venv\Scripts\python.exe"

# 3. Monta a lista de extras
if ($All) { $Extras = @("computer", "voice", "piper", "vision", "dev") }
$spec = "."
if ($Extras.Count -gt 0) { $spec = ".[{0}]" -f ($Extras -join ",") }

Write-Host "Instalando: pip install -e `"$spec`"" -ForegroundColor Yellow
& $vpy -m pip install --upgrade pip --quiet
& $vpy -m pip install -e $spec

# 4. .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env criado a partir do exemplo." -ForegroundColor Green
}

# 5. Ollama
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "Ollama encontrado." -ForegroundColor Green
    if ($PullModels) {
        Write-Host "Baixando modelos (pode demorar)..." -ForegroundColor Yellow
        & (Join-Path $root "scripts\pull_models.ps1")
    }
} else {
    Write-Host "Ollama NAO encontrado. Baixe em https://ollama.com/download" -ForegroundColor Red
}

Write-Host ""
Write-Host "Pronto!" -ForegroundColor Cyan
Write-Host "  1) ollama serve            (em outro terminal, se ainda nao estiver rodando)"
if (-not $PullModels) { Write-Host "  2) .\scripts\pull_models.ps1   (baixar modelos)" }
Write-Host "  3) .\.venv\Scripts\python.exe -m aila.main"
Write-Host "  -> http://localhost:8770" -ForegroundColor Green
