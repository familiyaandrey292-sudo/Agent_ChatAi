$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Checking Gateway health..."

$healthResponse = Invoke-WebRequest `
    -Uri "http://127.0.0.1:8765/v1/health" `
    -UseBasicParsing `
    -TimeoutSec 5

$health = $healthResponse.Content | ConvertFrom-Json

if (-not $health.ok) {
    throw "Gateway health check failed."
}

Write-Host "Health: OK"
Write-Host ("Paired: " + $health.paired)
Write-Host ("Browser auth: " + $health.browser_auth)

Write-Host "Checking authentication challenge..."

$challengeResponse = Invoke-WebRequest `
    -Uri "http://127.0.0.1:8765/v1/auth/challenge" `
    -UseBasicParsing `
    -TimeoutSec 5

$challenge = $challengeResponse.Content | ConvertFrom-Json

if (-not $challenge.challenge) {
    throw "Gateway did not return an authentication challenge."
}

Write-Host "Challenge endpoint: OK"
Write-Host "Challenge length: $($challenge.challenge.Length)"

Write-Host ""
Write-Host "Smoke test passed."
