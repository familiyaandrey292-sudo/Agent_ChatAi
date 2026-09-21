$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$checks = [System.Collections.Generic.List[string]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

function Pass($name, $detail) {
    $checks.Add(("PASS  {0}: {1}" -f $name, $detail))
}

function Fail($name, $detail) {
    $checks.Add(("FAIL  {0}: {1}" -f $name, $detail))
    $failures.Add($name)
}

Write-Host "=== Agent ChatAI Doctor ==="
Write-Host ""

# Python
$python = Get-Command python.exe -ErrorAction SilentlyContinue

if ($python) {
    $version = (& python --version 2>&1 | Out-String).Trim()
    Pass "Python" $version
}
else {
    Fail "Python" "python.exe not found"
}

# cryptography
if ($python) {
    $cryptoVersion = (
        & python -c "import cryptography; print(cryptography.__version__)" 2>&1 |
        Out-String
    ).Trim()

    if ($LASTEXITCODE -eq 0) {
        Pass "cryptography" $cryptoVersion
    }
    else {
        Fail "cryptography" $cryptoVersion
    }
}

# Gateway process
$gatewayListeners = @(
    Get-NetTCPConnection `
        -LocalPort 8765 `
        -State Listen `
        -ErrorAction SilentlyContinue
)

$process = $null

if ($gatewayListeners.Count -gt 0) {
    $ownerPid = [int]$gatewayListeners[0].OwningProcess

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

if ($process) {
    Pass "Gateway process" ("PID " + $process.Id)
}
else {
    Fail "Gateway process" "not running"
}

# Gateway port
$listening = [bool](
    Get-NetTCPConnection `
        -LocalPort 8765 `
        -State Listen `
        -ErrorAction SilentlyContinue
)

if ($listening) {
    Pass "Gateway port" "127.0.0.1:8765 listening"
}
else {
    Fail "Gateway port" "not listening"
}

# Health
$health = $null

if ($listening) {
    try {
        $healthResponse = Invoke-WebRequest `
            -Uri "http://127.0.0.1:8765/v1/health" `
            -UseBasicParsing `
            -TimeoutSec 5

        $health = $healthResponse.Content | ConvertFrom-Json

        if ($health.ok) {
            Pass "Health" "OK"
        }
        else {
            Fail "Health" "ok=false"
        }

        if ($health.paired -and $health.browser_auth) {
            Pass "Browser auth" "paired and enabled"
        }
        else {
            Fail "Browser auth" "pairing/authentication incomplete"
        }
    }
    catch {
        Fail "Health" $_.Exception.Message
    }
}

# Challenge
if ($listening -and $health -and $health.browser_auth) {
    try {
        $challengeResponse = Invoke-WebRequest `
            -Uri "http://127.0.0.1:8765/v1/auth/challenge" `
            -UseBasicParsing `
            -TimeoutSec 5

        $challenge = $challengeResponse.Content | ConvertFrom-Json

        if ($challenge.challenge) {
            Pass "Auth challenge" (
                "available, length " + $challenge.challenge.Length
            )
        }
        else {
            Fail "Auth challenge" "challenge missing"
        }
    }
    catch {
        Fail "Auth challenge" $_.Exception.Message
    }
}

# Persistent state
if (Test-Path ".\gateway\result_signing_key.pem") {
    Pass "Result signing key" "present"
}
else {
    Fail "Result signing key" "missing"
}

if (Test-Path ".\gateway\browser_auth_public.pem") {
    Pass "Browser auth key" "present"
}
else {
    Fail "Browser auth key" "missing"
}

if (Test-Path ".\gateway\replay.sqlite3") {
    Pass "Replay database" "present"
}
else {
    Fail "Replay database" "missing"
}


# Audit log
$auditPath = ".\gateway\audit.jsonl"

if (-not (Test-Path $auditPath)) {
    Pass "Audit log" "not created yet"
}
else {
    try {
        $auditLines = @(
            Get-Content $auditPath -Tail 200
        )

        $auditFailed = $false
        $auditFailure = ""

        foreach ($line in $auditLines) {
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }

            try {
                $entry = $line | ConvertFrom-Json
            }
            catch {
                $auditFailed = $true
                $auditFailure = "invalid JSONL"
                break
            }

            $propertyNames = @(
                $entry.PSObject.Properties.Name
            )

            if (
                $propertyNames -notcontains "timestamp" -or
                $propertyNames -notcontains "event"
            ) {
                $auditFailed = $true
                $auditFailure = "missing timestamp/event"
                break
            }

            if (
                $propertyNames -contains "args" -or
                $propertyNames -contains "result"
            ) {
                $auditFailed = $true
                $auditFailure = "sensitive payload fields detected"
                break
            }
        }

        if ($auditFailed) {
            Fail "Audit log" $auditFailure
        }
        else {
            Pass "Audit log" (
                "valid JSONL, " +
                $auditLines.Count +
                " recent lines checked"
            )
        }
    }
    catch {
        Fail "Audit log" $_.Exception.Message
    }
}

# Task Scheduler
$task = Get-ScheduledTask `
    -TaskName "Agent ChatAI Gateway" `
    -ErrorAction SilentlyContinue

if ($task) {
    $taskInfo = Get-ScheduledTaskInfo `
        -TaskName "Agent ChatAI Gateway"

    if ($taskInfo.LastTaskResult -eq 0) {
        Pass "Autostart task" (
            $task.State.ToString() +
            ", last result 0"
        )
    }
    elseif ($taskInfo.LastTaskResult -eq 267009) {
        Pass "Autostart task" (
            $task.State.ToString() +
            ", currently running"
        )
    }
    else {
        Fail "Autostart task" (
            "last result " +
            $taskInfo.LastTaskResult
        )
    }
}
else {
    Fail "Autostart task" "not installed"
}

# Extension files
$extensionFiles = @(
    ".\browser_bridge\extension\manifest.json"
    ".\browser_bridge\extension\background.js"
    ".\browser_bridge\extension\browser_keys.js"
    ".\browser_bridge\extension\content.js"
    ".\browser_bridge\extension\popup.html"
    ".\browser_bridge\extension\popup.js"
    ".\browser_bridge\extension\result_public_key.js"
)

$missingExtensionFiles = @()

foreach ($file in $extensionFiles) {
    if (-not (Test-Path $file)) {
        $missingExtensionFiles += $file
    }
}

if ($missingExtensionFiles.Count -eq 0) {
    Pass "Browser extension" "all required files present"
}
else {
    Fail "Browser extension" (
        "missing: " +
        ($missingExtensionFiles -join ", ")
    )
}

# JavaScript syntax
$node = Get-Command node.exe -ErrorAction SilentlyContinue

if ($node) {
    $jsFiles = @(
        ".\browser_bridge\extension\background.js"
        ".\browser_bridge\extension\browser_keys.js"
        ".\browser_bridge\extension\content.js"
        ".\browser_bridge\extension\popup.js"
    )

    $jsFailed = $false

    foreach ($file in $jsFiles) {
        & node --check $file 2>$null

        if ($LASTEXITCODE -ne 0) {
            $jsFailed = $true
            Fail "JavaScript" "$file failed syntax check"
        }
    }

    if (-not $jsFailed) {
        Pass "JavaScript" "all syntax checks passed"
    }
}
else {
    Fail "JavaScript" "node.exe not found"
}

# Python compilation
if ($python) {
    $compileOutput = @(
        & python -m py_compile `
            .\gateway\server.py `
            .\gateway\audit.py `
            .\gateway\browser_auth.py `
            .\gateway\pairing.py `
            .\gateway\confirmation.py `
            .\gateway\executor.py `
            .\gateway\gateway.py 2>&1
    )

    $compileExit = $LASTEXITCODE

    if ($compileExit -eq 0) {
        Pass "Python compilation" "Gateway modules compile"
    }
    else {
        Fail "Python compilation" (
            (
                $compileOutput -join "`r`n"
            ).Trim()
        )
    }
}

# Full tests
if ($python) {
    $testLog = Join-Path $env:TEMP "agent_chatai_doctor_tests.log"

    & python -m unittest discover -s tests -q `
        > $testLog 2>&1

    if ($LASTEXITCODE -eq 0) {
        $summary = (
            Get-Content $testLog -Raw
        ).Trim()

        $match = [regex]::Match(
            $summary,
            'Ran\s+(\d+)\s+tests.*?\nOK',
            [System.Text.RegularExpressions.RegexOptions]::Singleline
        )

        if ($match.Success) {
            Pass "Test suite" (
                $match.Groups[1].Value + " tests, OK"
            )
        }
        else {
            Pass "Test suite" "completed successfully"
        }
    }
    else {
        Fail "Test suite" (
            Get-Content $testLog -Raw
        ).Trim()
    }
}

Write-Host ""
Write-Host "=== Results ==="

foreach ($line in $checks) {
    Write-Host $line
}

Write-Host ""

if ($failures.Count -eq 0) {
    Write-Host "DOCTOR: PASS"
    exit 0
}
else {
    Write-Host (
        "DOCTOR: FAIL (" +
        $failures.Count +
        " checks failed)"
    )
    exit 1
}
