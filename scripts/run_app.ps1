param(
    [switch]$SkipBuild,
    [switch]$Lan
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\node_tools.ps1")
Ensure-NodePath

$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "server-frontend"
$Backend = Join-Path $Root "server-backend"
$Scripts = Join-Path $Root "scripts"
$Port = 8000
$BindHost = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
$Scheme = "http"
$UvicornSslArgs = @()

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

# Keep scan art-hash deps present in the project venv.
& $Python -m pip install -q "Pillow>=10.0.0"

$listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
    Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

if ($Lan) {
    # Mobile cameras require a secure context; HTTP on a LAN IP leaves mediaDevices undefined.
    & $Python -m pip install -q "cryptography>=42.0.0"
    $tlsOut = & $Python (Join-Path $Scripts "ensure_lan_tls.py") --dir (Join-Path $Root "data\lan_tls")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create LAN TLS certificate"
    }
    $certPath = ($tlsOut | Select-Object -First 1).ToString().Trim()
    $keyPath = ($tlsOut | Select-Object -Skip 1 -First 1).ToString().Trim()
    if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
        throw "LAN TLS certificate files were not created"
    }
    $Scheme = "https"
    $UvicornSslArgs = @("--ssl-certfile", $certPath, "--ssl-keyfile", $keyPath)

    Write-Host "LAN mode: binding to ${BindHost}:${Port} (HTTPS for camera access)"
    Write-Host "Open on this PC:  ${Scheme}://127.0.0.1:${Port}"
    $lanAddresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.PrefixOrigin -ne "WellKnown" -and
            $_.AddressState -eq "Preferred"
        } |
        Select-Object -ExpandProperty IPAddress -Unique
    if ($lanAddresses) {
        Write-Host "Open on other devices on this network:"
        foreach ($ip in $lanAddresses) {
            Write-Host "  ${Scheme}://${ip}:${Port}"
        }
    }
    else {
        Write-Host "Could not detect a LAN IPv4 address; check ipconfig and use ${Scheme}://<your-ip>:${Port}"
    }
    Write-Host "Accept the self-signed certificate warning once on your phone (required for the camera)."
    Write-Host "If phones/PCs cannot connect, allow Windows Firewall inbound TCP ${Port} (or Python)."
}

& $Python -m uvicorn api.main:app --host $BindHost --port $Port @UvicornSslArgs
