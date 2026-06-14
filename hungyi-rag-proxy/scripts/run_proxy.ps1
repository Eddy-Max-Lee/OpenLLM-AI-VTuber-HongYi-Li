$ErrorActionPreference = "Stop"

$ProxyPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProxyPath

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    Write-Host "[HUMAN ACTION REQUIRED]"
    Write-Host "Proxy virtual environment is missing. Run .\scripts\setup_all.ps1 first."
    exit 1
}

& .\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8765 --reload

