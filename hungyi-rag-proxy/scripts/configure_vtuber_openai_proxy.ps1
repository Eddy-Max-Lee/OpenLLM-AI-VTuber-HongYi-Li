$ErrorActionPreference = "Stop"

$TargetPath = "E:\VTUBER\hong-yi"
$OpenVtuberPath = Join-Path $TargetPath "Open-LLM-VTuber"
$ConfPath = Join-Path $OpenVtuberPath "conf.yaml"
$TemplatePath = Join-Path $OpenVtuberPath "config_templates\conf.ZH.default.yaml"
$NotesPath = Join-Path $TargetPath "hungyi-rag-proxy\CONFIG_PATCH_NOTES.md"

function Write-ManualNotes {
    $Message = @"
# Manual Open-LLM-VTuber Config Patch

Could not safely patch ``conf.yaml`` automatically.

Set these values manually:

````yaml
character_config:
  persona_prompt: |
    You are an unofficial AI machine-learning teaching assistant inspired by Professor Hung-Yi Lee's public teaching style.
    You are not Professor Hung-Yi Lee, not official, and not endorsed by him.
    Answer in Traditional Chinese.
    Prefer this teaching structure: intuition -> black box -> mechanism -> common misunderstandings -> recap.
    Never claim to be Professor Hung-Yi Lee.
  agent_config:
    agent_settings:
      basic_memory_agent:
        llm_provider: 'openai_compatible_llm'
    llm_configs:
      openai_compatible_llm:
        base_url: 'http://127.0.0.1:8765/v1'
        llm_api_key: 'not-needed'
        model: 'hungyi-rag-proxy'
````
"@
    Set-Content -LiteralPath $NotesPath -Encoding UTF8 -Value $Message
    Write-Host "[HUMAN ACTION REQUIRED]"
    Write-Host "Could not safely patch conf.yaml. See $NotesPath"
}

if (-not (Test-Path -LiteralPath $ConfPath)) {
    if (-not (Test-Path -LiteralPath $TemplatePath)) {
        Write-ManualNotes
        exit 1
    }
    Copy-Item -LiteralPath $TemplatePath -Destination $ConfPath
}

$BackupPath = "$ConfPath.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item -LiteralPath $ConfPath -Destination $BackupPath

$Text = Get-Content -Raw -Encoding UTF8 -LiteralPath $ConfPath
$Required = @("openai_compatible_llm:", "basic_memory_agent:", "persona_prompt:")
foreach ($Needle in $Required) {
    if (-not $Text.Contains($Needle)) {
        Write-ManualNotes
        exit 1
    }
}

$SafePersona = @"
  persona_prompt: |
    You are an unofficial AI machine-learning teaching assistant inspired by Professor Hung-Yi Lee's public teaching style.
    You are not Professor Hung-Yi Lee, not official, and not endorsed by him.
    Answer in Traditional Chinese.
    Prefer this teaching structure: intuition -> black box -> mechanism -> common misunderstandings -> recap.
    Never claim to be Professor Hung-Yi Lee.
    Remind users this is AI-generated teaching assistance when needed.
    This is an unofficial AI teaching assistant.
    It is inspired by Professor Hung-Yi Lee's teaching style.
    It is not Professor Hung-Yi Lee, not official, and not endorsed by him.
"@

$Text = [regex]::Replace($Text, "(?ms)^  persona_prompt: \|\r?\n.*?(?=^  #  =+)", $SafePersona + "`r`n`r`n", 1)
$Text = $Text -replace "llm_provider: '.*?'", "llm_provider: 'openai_compatible_llm'"
$Text = $Text -replace "(?ms)(openai_compatible_llm:\r?\n\s+base_url: )'.*?'", "`${1}'http://127.0.0.1:8765/v1'"
$Text = $Text -replace "(?ms)(openai_compatible_llm:\r?\n(?:.*\r?\n){1}\s+llm_api_key: )'.*?'", "`${1}'not-needed'"
$Text = $Text -replace "(?ms)(openai_compatible_llm:\r?\n(?:.*\r?\n){4}\s+model: )'.*?'", "`${1}'hungyi-rag-proxy'"

Set-Content -LiteralPath $ConfPath -Encoding UTF8 -Value $Text
Write-Host "Patched $ConfPath"
Write-Host "Backup created: $BackupPath"
