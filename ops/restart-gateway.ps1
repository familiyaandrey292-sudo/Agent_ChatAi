# Hard restart of the Gateway: kills whatever process holds port 8765 (Stop-ScheduledTask
# alone does NOT kill an already-running python.exe), then starts fresh code via ops script.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$oldPids = @()
$listeners = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
foreach ($l in $listeners) { if ($l.OwningProcess) { $oldPids += [int]$l.OwningProcess } }
$fallback = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'gateway\.server|gateway/server' }
foreach ($p in $fallback) { if ($p.ProcessId -notin $oldPids) { $oldPids += [int]$p.ProcessId } }

if ($oldPids.Count -eq 0) {
    Write-Host "No gateway process found running."
} else {
    foreach ($procId in $oldPids) {
        Write-Host ("Killing stale gateway PID {0}" -f $procId)
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

Stop-ScheduledTask -TaskName "Agent ChatAI Gateway" -ErrorAction SilentlyContinue

powershell -ExecutionPolicy Bypass -File .\ops\start-gateway.ps1

Start-Sleep -Seconds 2
$newPid = (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1).OwningProcess
Write-Host ("New gateway PID: {0}" -f $newPid)
try {
    $health = Invoke-RestMethod http://127.0.0.1:8765/v1/health
    Write-Host ("Health: {0}" -f ($health | ConvertTo-Json -Compress))
} catch {
    Write-Host ("HEALTH ERROR: {0}" -f $_)
}
