$ErrorActionPreference = "Stop"

$TaskName = "Agent ChatAI Gateway"

Unregister-ScheduledTask `
    -TaskName $TaskName `
    -Confirm:$false `
    -ErrorAction SilentlyContinue

Write-Host "Autostart removed."
