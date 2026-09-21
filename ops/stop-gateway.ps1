$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-GatewayProcessIds {
    $ids = @()

    $listeners = Get-NetTCPConnection `
        -LocalPort 8765 `
        -State Listen `
        -ErrorAction SilentlyContinue

    foreach ($listener in $listeners) {
        if ($listener.OwningProcess -and
            $listener.OwningProcess -notin $ids) {
            $ids += [int]$listener.OwningProcess
        }
    }

    $fallback = Get-CimInstance Win32_Process `
        -Filter "Name='python.exe'" |
        Where-Object {
            $_.CommandLine -match 'gateway\.server'
        }

    foreach ($process in $fallback) {
        if ($process.ProcessId -notin $ids) {
            $ids += [int]$process.ProcessId
        }
    }

    return $ids
}

$processIds = @(Get-GatewayProcessIds)

if ($processIds.Count -eq 0) {
    Write-Host "Gateway is not running."
    exit 0
}

foreach ($processId in $processIds) {
    $process = Get-Process `
        -Id $processId `
        -ErrorAction SilentlyContinue

    if ($process -and $process.ProcessName -eq "python") {
        Stop-Process `
            -Id $processId `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

$deadline = (Get-Date).AddSeconds(10)

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250

    $remaining = @(
        Get-NetTCPConnection `
            -LocalPort 8765 `
            -State Listen `
            -ErrorAction SilentlyContinue
    )

    if ($remaining.Count -eq 0) {
        Write-Host "Gateway stopped."
        exit 0
    }
}

$remainingIds = @(
    Get-NetTCPConnection `
        -LocalPort 8765 `
        -State Listen `
        -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess
)

throw (
    "Gateway did not stop within 10 seconds. " +
    "Port 8765 owner PID(s): " +
    ($remainingIds -join ", ")
)
