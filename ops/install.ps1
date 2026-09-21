$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Agent ChatAI Gateway - install check"

if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) {
    throw "Python is not available in PATH."
}

$pythonVersion = (& python --version 2>&1 | Out-String).Trim()
Write-Host "Python: $pythonVersion"

& python -c "import cryptography; print('cryptography:', cryptography.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "Python package 'cryptography' is unavailable."
}

$required = @(
    ".\gateway\server.py"
    ".\gateway\browser_auth.py"
    ".\gateway\pairing.py"
    ".\gateway\signing.py"
    ".\gateway\confirmation.py"
    ".\gateway\replay_store.py"
    ".\gateway\audit.py"
    ".\gateway\gateway.py"
    ".\browser_bridge\extension\manifest.json"
    ".\browser_bridge\extension\background.js"
    ".\browser_bridge\extension\browser_keys.js"
    ".\browser_bridge\extension\content.js"
    ".\browser_bridge\extension\popup.html"
    ".\browser_bridge\extension\popup.js"
    ".\browser_bridge\extension\result_public_key.js"
)

foreach ($file in $required) {
    if (-not (Test-Path $file)) {
        throw "Required file is missing: $file"
    }
}

Write-Host "Compiling Gateway..."
& python -m py_compile `
    .\gateway\server.py `
    .\gateway\browser_auth.py `
    .\gateway\pairing.py `
    .\gateway\signing.py `
    .\gateway\confirmation.py `
    .\gateway\replay_store.py `
    .\gateway\gateway.py `
    .\gateway\audit.py

if ($LASTEXITCODE -ne 0) {
    throw "Gateway Python compilation failed."
}

if (Get-Command node.exe -ErrorAction SilentlyContinue) {
    Write-Host "Checking extension JavaScript..."
    & node --check .\browser_bridge\extension\background.js
    & node --check .\browser_bridge\extension\browser_keys.js
    & node --check .\browser_bridge\extension\content.js
    & node --check .\browser_bridge\extension\popup.js
}

Write-Host "Running test suite..."
& python -m unittest discover -s tests -q

if ($LASTEXITCODE -ne 0) {
    throw "Test suite failed."
}

Write-Host ""
Write-Host "Installation check completed successfully."
Write-Host "Existing keys/databases were not modified."
