# ============================================================
#  Aila - setup do ambiente (Windows / PowerShell)
# ============================================================
$ErrorActionPreference = "Stop"

Write-Host "== Aila setup ==" -ForegroundColor Cyan

# 1. Ambiente virtual
if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Yellow
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

# 2. Dependências
Write-Host "Instalando dependencias base..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -e .

# 3. Arquivo .env
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Arquivo .env criado a partir do exemplo." -ForegroundColor Green
}

# 4. Verifica Ollama
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "Ollama encontrado: $($ollama.Source)" -ForegroundColor Green
} else {
    Write-Host "Ollama NAO encontrado. Baixe em https://ollama.com/download" -ForegroundColor Red
}

Write-Host ""
Write-Host "Pronto! Proximos passos:" -ForegroundColor Cyan
Write-Host "  1) ollama serve            (em outro terminal)"
Write-Host "  2) .\scripts\pull_models.ps1"
Write-Host "  3) python -m aila.main"
