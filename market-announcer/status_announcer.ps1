$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $Root "announcer.pid"

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "BTC announcer is not running: PID file not found."
    exit 0
}

$PidText = (Get-Content -Raw -LiteralPath $PidFile).Trim()
$Process = if ($PidText) { Get-Process -Id ([int]$PidText) -ErrorAction SilentlyContinue } else { $null }

if ($Process) {
    Write-Host "BTC announcer is running. PID: $PidText"
} else {
    Write-Host "BTC announcer PID file exists, but process is not running. PID: $PidText"
}

