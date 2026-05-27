param(
    [int]$Port = 5000,
    [switch]$Production = $false
)

$env:BASE_URL = if ($env:BASE_URL) { $env:BASE_URL } else { "http://localhost:$Port" }

if (-not (Test-Path "venv")) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Yellow
    python -m venv venv
}

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$venvPip = Join-Path $PSScriptRoot "venv\Scripts\pip.exe"

Write-Host "Instalando dependencias..." -ForegroundColor Yellow
& $venvPip install -q -r requirements.txt

Write-Host ""
Write-Host "============================================" -ForegroundColor Black -BackgroundColor White
Write-Host "  DK ELECTRIC HELP - Sistema de Orcamentos" -ForegroundColor White -BackgroundColor Black
Write-Host "============================================" -ForegroundColor Black -BackgroundColor White
Write-Host ""
Write-Host "  URL Base: $env:BASE_URL" -ForegroundColor Cyan
Write-Host "  Porta:    $Port" -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================" -ForegroundColor Black -BackgroundColor White
Write-Host ""

$env:FLASK_APP = "app.py"
$env:FLASK_ENV = if ($Production) { "production" } else { "development" }

if ($Production) {
    & $venvPython -m gunicorn --bind "0.0.0.0:$Port" --workers 4 app:app
} else {
    & $venvPython app.py
}
