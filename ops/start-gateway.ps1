$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$stateDir = Join-Path $env:LOCALAPPDATA "AgentChatAI"
$logDir = Join-Path $stateDir "logs"

New-Item -ItemType Directory -Force $logDir | Out-Null

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

$existingIds = @(Get-GatewayProcessIds)

if ($existingIds.Count -gt 0) {
    $existingPython = @(
        $existingIds |
        ForEach-Object {
            Get-Process -Id $_ -ErrorAction SilentlyContinue
        } |
        Where-Object {
            $_.ProcessName -eq "python"
        }
    )

    if ($existingPython.Count -gt 0) {
        Write-Host "Gateway is already running."
        Write-Host ("PID: " + ($existingPython[0].Id))
        exit 0
    }

    throw (
        "Port 8765 is already occupied by PID(s): " +
        ($existingIds -join ", ")
    )
}

$outLog = Join-Path $logDir "gateway.out.log"
$errLog = Join-Path $logDir "gateway.err.log"

Remove-Item $outLog, $errLog -Force -ErrorAction SilentlyContinue

$python = (Get-Command python.exe -ErrorAction Stop).Source

$process = Start-Process `
    -FilePath $python `
    -ArgumentList @("-u", "-m", "gateway.server") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

$deadline = (Get-Date).AddSeconds(10)

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250

    $listeners = @(
        Get-NetTCPConnection `
            -LocalPort 8765 `
            -State Listen `
            -ErrorAction SilentlyContinue
    )

    if ($listeners.Count -gt 0) {
        Write-Host "Gateway started."
        Write-Host "PID: $($process.Id)"
        Write-Host "URL: http://127.0.0.1:8765"
        Write-Host "Logs: $logDir"
        exit 0
    }

    if (-not (Get-Process `
        -Id $process.Id `
        -ErrorAction SilentlyContinue)) {
        break
    }
}

$err = if (Test-Path $errLog) {
    Get-Content $errLog -Raw
}
else {
    ""
}

if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
    Stop-Process `
        -Id $process.Id `
        -Force `
        -ErrorAction SilentlyContinue
}

throw "Gateway failed to start within 10 seconds. $err"
