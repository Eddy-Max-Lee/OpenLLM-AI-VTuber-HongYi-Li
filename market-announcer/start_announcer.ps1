$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root "..\Open-LLM-VTuber\.venv\Scripts\python.exe"
$Script = Join-Path $Root "btc_price_announcer.py"
$PidFile = Join-Path $Root "announcer.pid"
$OutLog = Join-Path $Root "announcer.out.log"
$ErrLog = Join-Path $Root "announcer.err.log"

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = (Get-Content -Raw -LiteralPath $PidFile).Trim()
    if ($ExistingPid -and (Get-Process -Id ([int]$ExistingPid) -ErrorAction SilentlyContinue)) {
        Write-Host "BTC announcer is already running. PID: $ExistingPid"
        exit 0
    }
    Remove-Item -LiteralPath $PidFile -Force
}

$Args = @("-u", $Script, "--pid-file", $PidFile)
$Process = Start-Process -FilePath $Python `
    -ArgumentList $Args `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 1
Write-Host "BTC announcer started. PID: $($Process.Id)"
Write-Host "Logs:"
Write-Host "  $OutLog"
Write-Host "  $ErrLog"
