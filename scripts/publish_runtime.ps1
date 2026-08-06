# Copy an already-built frontend into runtime/frontend for the LAN service.
# Does not run npm build — fail if server-frontend/dist is missing.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $Root "server-frontend\dist"
$Runtime = Join-Path $Root "runtime"
$Target = Join-Path $Runtime "frontend"
$Index = Join-Path $Source "index.html"

if (-not (Test-Path $Index)) {
    throw "Frontend build not found at $Index. Run .\scripts\build_frontend.ps1 first (or npm run build in server-frontend)."
}

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Runtime "tls") | Out-Null

if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
}
New-Item -ItemType Directory -Force -Path $Target | Out-Null

Copy-Item -Path (Join-Path $Source "*") -Destination $Target -Recurse -Force

Write-Host "Published frontend artifact to $Target"
