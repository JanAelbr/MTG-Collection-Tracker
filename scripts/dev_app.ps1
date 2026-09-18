param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\node_tools.ps1")
Ensure-NodePath

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "server-backend"
$Scripts = Join-Path $Root "scripts"
$Collection = Join-Path $Root "server-backend\collection"
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw @"
Project venv not found at $Python.

Create it first:
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
"@
}

if ($Install) {
    $env:PYO3_USE_ABI3_FORWARD_COMPATIBILITY = "1"
    & $Python -m pip install -r (Join-Path $Root "requirements.txt")
    Push-Location (Join-Path $Root "server-frontend")
    npm install
    Pop-Location
}

$env:PYTHONPATH = "$Backend;$Scripts;$Collection"
$apiProc = Start-Process `
    -FilePath $Python `
    -ArgumentList @("run_api.py") `
    -WorkingDirectory $Backend `
    -PassThru `
    -NoNewWindow

function Stop-ApiProcess {
    if (-not $apiProc -or $apiProc.HasExited) {
        return
    }
    & taskkill.exe /PID $apiProc.Id /T /F 2>$null | Out-Null
}

try {
    $ready = $false
    foreach ($unused in 1..50) {
        if ($apiProc.HasExited) {
            throw "API exited before listening on port 8000 (exit $($apiProc.ExitCode))."
        }
        $listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($listening) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) {
        Stop-ApiProcess
        throw "API did not start listening on port 8000."
    }

    Push-Location (Join-Path $Root "server-frontend")
    try {
        npm run dev
    }
    finally {
        Pop-Location
    }
}
finally {
    Stop-ApiProcess
}
