$ErrorActionPreference = "Stop"

$TargetPath = "E:\VTUBER\hong-yi"
$OpenVtuberPath = Join-Path $TargetPath "Open-LLM-VTuber"
Set-Location $OpenVtuberPath

Write-Host "Open http://localhost:12393 after the server starts."
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv run run_server.py
} else {
    Write-Host "[HUMAN ACTION REQUIRED]"
    Write-Host "uv is not installed or not on PATH. Install uv, then run:"
    Write-Host "uv run run_server.py"
    exit 1
}

