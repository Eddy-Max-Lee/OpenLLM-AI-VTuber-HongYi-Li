$ErrorActionPreference = "Stop"

$Health = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8765/health"
Write-Host "Health:"
$Health | ConvertTo-Json -Depth 5

$Payload = (@{
    model = "hungyi-rag-proxy"
    stream = $false
    messages = @(
        @{
            role = "user"
            content = "Explain attention in Traditional Chinese with the configured teaching style, and do not impersonate Professor Hung-Yi Lee."
        }
    )
} | ConvertTo-Json -Depth 10)

$Response = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/v1/chat/completions" -ContentType "application/json" -Body $Payload
$Text = $Response.choices[0].message.content
if ($Text.Length -gt 1000) {
    $Text = $Text.Substring(0, 1000)
}
Write-Host ""
Write-Host "Response first 1000 chars:"
Write-Host $Text
