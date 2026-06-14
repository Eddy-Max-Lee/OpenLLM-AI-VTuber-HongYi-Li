$ErrorActionPreference = "Stop"

$TargetPath = "E:\VTUBER\hong-yi"
$ProxyPath = Join-Path $TargetPath "hungyi-rag-proxy"
$OpenVtuberPath = Join-Path $TargetPath "Open-LLM-VTuber"
$SkillPath = Join-Path $TargetPath "hung-yi-lee-skill"

if (-not (Test-Path -LiteralPath $TargetPath)) {
    throw "TARGET_PATH not found: $TargetPath"
}
if (-not (Test-Path -LiteralPath $OpenVtuberPath)) {
    Write-Warning "Missing Open-LLM-VTuber. Clone it before running the full MVP."
}
if (-not (Test-Path -LiteralPath $SkillPath)) {
    Write-Warning "Missing hung-yi-lee-skill. Clone it before running the full MVP."
}

Set-Location $ProxyPath
if (-not (Test-Path -LiteralPath ".venv")) {
    py -3 -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created .env from .env.example."
} else {
    Write-Host ".env already exists; leaving it unchanged."
}

Write-Host ""
Write-Host "[HUMAN ACTION REQUIRED]"
Write-Host "Review hungyi-rag-proxy\.env and set the upstream LLM fields before expecting real answers."
Write-Host "For Ollama: UPSTREAM_MODE=ollama_native and OLLAMA_MODEL=qwen2.5:latest."
Write-Host "For an API: UPSTREAM_MODE=openai_compatible, UPSTREAM_BASE_URL, UPSTREAM_API_KEY, UPSTREAM_MODEL."

