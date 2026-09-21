$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$TaskName = "Agent ChatAI Gateway"

$listeners = @(
    Get-NetTCPConnection `
        -LocalPort 8765 `
        -State Listen `
        -ErrorAction SilentlyContinue
)

$process = $null

if ($listeners.Count -gt 0) {
    $ownerPid = [int]$listeners[0].OwningProcess
    $process = Get-Process `
        -Id $ownerPid `
        -ErrorAction SilentlyContinue
}

if (-not $process) {
    $process = Get-CimInstance Win32_Process `
        -Filter "Name='python.exe'" |
        Where-Object {
            $_.CommandLine -match 'gateway\.server'
        } |
        Select-Object -First 1
}

$listening = ($listeners.Count -gt 0)

$task = Get-ScheduledTask `
    -TaskName $TaskName `
    -ErrorAction SilentlyContinue

$taskInfo = $null

if ($task) {
    $taskInfo = Get-ScheduledTaskInfo `
        -TaskName $TaskName
}

if ($process) {
    $processStatus = "running (PID " + $process.Id + ")"
}
else {
    $processStatus = "not running"
}

if ($listening) {
    $portStatus = "127.0.0.1:8765 listening"
}
else {
    $portStatus = "not listening"
}

if (Test-Path ".\gateway\result_signing_key.pem") {
    $signingStatus = "present"
}
else {
    $signingStatus = "MISSING"
}

if (Test-Path ".\gateway\browser_auth_public.pem") {
    $browserStatus = "paired"
}
else {
    $browserStatus = "not paired"
}

if (Test-Path ".\gateway\replay.sqlite3") {
    $replayStatus = "present"
}
else {
    $replayStatus = "MISSING"
}

Write-Host ("Gateway process: " + $processStatus)
Write-Host ("Gateway port:    " + $portStatus)
Write-Host ("Signing key:     " + $signingStatus)
Write-Host ("Browser key:     " + $browserStatus)
Write-Host ("Replay database: " + $replayStatus)

if ($task) {
    Write-Host ""
    Write-Host ("Scheduled task:  " + $task.State)

    if ($taskInfo) {
        $code = [int64]$taskInfo.LastTaskResult

        if ($code -eq 0) {
            $taskResult = "0 (success)"
        }
        elseif ($code -eq 267009) {
            $taskResult = "267009 (0x41301 = task is currently running)"
        }
        else {
            $taskResult = [string]$code
        }

        Write-Host ("Last run:        " + $taskInfo.LastRunTime)
        Write-Host ("Last result:     " + $taskResult)
    }
}
else {
    Write-Host ""
    Write-Host "Scheduled task:  NOT INSTALLED"
}

if ($listening) {
    try {
        $healthResponse = Invoke-WebRequest `
            -Uri "http://127.0.0.1:8765/v1/health" `
            -UseBasicParsing `
            -TimeoutSec 5

        Write-Host ""
        Write-Host "Health:"
        Write-Host $healthResponse.Content
    }
    catch {
        Write-Host ""
        Write-Host (
            "Health check failed: " +
            $_.Exception.Message
        )
    }
}
