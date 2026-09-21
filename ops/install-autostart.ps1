$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$StartScript = Join-Path $Root "ops\start-gateway.ps1"

$TaskName = "Agent ChatAI Gateway"

if (-not (Test-Path $StartScript)) {
    throw "Missing start script: $StartScript"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument (
        '-NoProfile -ExecutionPolicy Bypass -File "' +
        $StartScript +
        '"'
    )

$trigger = New-ScheduledTaskTrigger `
    -AtLogOn `
    -User "$env:USERDOMAIN\$env:USERNAME"

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Force | Out-Null

Write-Host "Autostart installed."
Write-Host "Task: $TaskName"
Write-Host "Trigger: at user logon"
Write-Host "Run level: Limited"
