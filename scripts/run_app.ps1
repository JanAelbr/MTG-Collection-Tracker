param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\node_tools.ps1")
Ensure-NodePath

$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "server-frontend"
$Backend = Join-Path $Root "server-backend"
$Scripts = Join-Path $Root "scripts"

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

if (-not $SkipBuild) {
    Push-Location $Frontend
    try {
        if (-not (Test-Path "node_modules")) {
            npm install
        }
        npm run build
    }
    finally {
        Pop-Location
    }
}

$Collection = Join-Path $Root "server-backend\collection"

$env:PYTHONPATH = "$Backend;$Scripts;$Collection"
Set-Location $Backend

$listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
    Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

& $Python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
