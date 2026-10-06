# Recovery of Gateway runtime state (keys / replay DB / pairing) after loss.
# Usage:  powershell -ExecutionPolicy Bypass -File ops\recover-gateway-state.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "=== Agent ChatAI state recovery ===" -ForegroundColor Cyan

# 1) Sync code from GitHub WITHOUT git clean (runtime state is protected by .gitignore,
#    but we never wipe it anyway).
git fetch origin
git reset --hard origin/main

# 2) HARD STOP the real gateway process. Stop-ScheduledTask alone does NOT kill
#    an already-running process, and a stale python.exe keeps holding port 8765
#    with OLD code (no /v1/pairing-code) — which caused "not_found" errors.
$oldPids = @()
$listeners = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($l in $listeners) { if ($l.OwningProcess) { $oldPids += [int]$l.OwningProcess } }
$fallback = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'gateway\.server|gateway/server' }
foreach ($p in $fallback) { if ($p.ProcessId -notin $oldPids) { $oldPids += [int]$p.ProcessId } }
foreach ($pid2 in $oldPids) {
    Write-Host ("Killing stale gateway PID {0}" -f $pid2) -ForegroundColor Yellow
    Stop-Process -Id $pid2 -Force -ErrorAction SilentlyContinue
}
Stop-ScheduledTask -TaskName "Agent ChatAI Gateway" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Prefer the project venv interpreter (has pytest/cryptography); fall back to python on PATH.
$pyExe = "python"
if (Test-Path ".\.venv\Scripts\python.exe") { $pyExe = ".\.venv\Scripts\python.exe" }
& $pyExe -m pip install -q -r requirements.txt -r requirements-dev.txt

# Start via ops script (runs from repo root, correct interpreter).
powershell -ExecutionPolicy Bypass -File .\ops\start-gateway.ps1
Start-Sleep -Seconds 3

$health = Invoke-RestMethod http://127.0.0.1:8765/v1/health
Write-Host ("Health: {0}" -f ($health | ConvertTo-Json -Compress))

# 3) Fetch/reset the live pairing code and put it into the clipboard.
$pair = Invoke-RestMethod http://127.0.0.1:8765/v1/pairing-code
$code = if ($pair.code) { $pair.code } elseif ($pair.pairing_code) { $pair.pairing_code } else { $null }
if (-not $code) { throw "Gateway did not return a pairing code: $($pair | ConvertTo-Json -Compress)" }
Set-Clipboard -Value $code
Write-Host "Pairing code copied to clipboard: $code" -ForegroundColor Green

# 4) Verify files that previously went missing are back.
foreach ($f in @("gateway\result_signing_key.pem", "gateway\browser_auth_public.pem", "gateway\replay.sqlite3")) {
    if (Test-Path $f) { Write-Host "OK   $f" -ForegroundColor Green }
    else              { Write-Host "MISS $f" -ForegroundColor Yellow }
}

# 5) Full verification (same interpreter as the gateway).
& $pyExe -m pytest -q
.\ops\doctor.ps1

Write-Host ""
Write-Host "Next manual step: open the Bridge extension popup -> 'Gateway pairing code' -> Ctrl+V -> Pair." -ForegroundColor Cyan
