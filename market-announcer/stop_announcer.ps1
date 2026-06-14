$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root "announcer.pid"

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "BTC announcer PID file not found. It may not be running."
    exit 0
}

$PidText = (Get-Content -Raw -LiteralPath $PidFile).Trim()
if (-not $PidText) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "Empty PID file removed."
    exit 0
}

$Process = Get-Process -Id ([int]$PidText) -ErrorAction SilentlyContinue
if (-not $Process) {
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "BTC announcer process was not running. PID file removed."
    exit 0
}

Stop-Process -Id $Process.Id -Force
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Write-Host "BTC announcer stopped. PID: $PidText"

