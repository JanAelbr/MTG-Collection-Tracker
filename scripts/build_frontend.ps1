$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\node_tools.ps1")
Ensure-NodePath

$Root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $Root "server-frontend")
try {
    if (-not (Test-Path "node_modules")) {
        npm install
    }
    npm run build
}
finally {
    Pop-Location
}
