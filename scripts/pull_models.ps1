# ============================================================
#  Baixa os modelos recomendados para a RTX 4060 8GB
# ============================================================
$ErrorActionPreference = "Continue"

Write-Host "Baixando modelos via Ollama (pode demorar)..." -ForegroundColor Cyan

# Verifica se o Ollama esta rodando
try { Invoke-RestMethod "http://127.0.0.1:11434/api/version" -TimeoutSec 3 | Out-Null }
catch {
    Write-Host "Ollama nao esta rodando. Abra outro terminal e rode: ollama serve" -ForegroundColor Red
    exit 1
}

$models = @(
    "qwen2.5:7b-instruct",     # chat geral (recomendado)
    "deepseek-coder:6.7b"      # code agent (recomendado)
    # "llava:7b"               # descomente para o Vision Agent (Fase 3)
)

foreach ($m in $models) {
    Write-Host "→ pull $m" -ForegroundColor Yellow
    ollama pull $m
}

Write-Host "Concluido. Modelos disponiveis:" -ForegroundColor Green
ollama list
