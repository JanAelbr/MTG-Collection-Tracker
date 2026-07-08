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

if ($Install) {
    $env:PYO3_USE_ABI3_FORWARD_COMPATIBILITY = "1"
    pip install -r (Join-Path $Root "requirements.txt")
    Push-Location (Join-Path $Root "server-frontend")
    npm install
    Pop-Location
}

$apiJob = Start-Job -ScriptBlock {
    param($BackendDir, $ScriptsDir, $CollectionDir)
    $env:PYTHONPATH = "$BackendDir;$ScriptsDir;$CollectionDir"
    Set-Location $BackendDir
    python run_api.py
} -ArgumentList $Backend, $Scripts, $Collection

Push-Location (Join-Path $Root "server-frontend")
try {
    npm run dev
}
finally {
    Pop-Location
    Stop-Job $apiJob -ErrorAction SilentlyContinue
    Remove-Job $apiJob -Force -ErrorAction SilentlyContinue
}
