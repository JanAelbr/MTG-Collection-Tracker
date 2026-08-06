# Start the LAN runtime service: uvicorn on 0.0.0.0:8080 with HTTPS.
# Serves the published artifact at runtime/frontend; logs to runtime/logs.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "server-backend"
$Scripts = Join-Path $Root "scripts"
$Collection = Join-Path $Root "server-backend\collection"
$Runtime = Join-Path $Root "runtime"
$Frontend = Join-Path $Runtime "frontend"
$TlsDir = Join-Path $Runtime "tls"
$LogsDir = Join-Path $Runtime "logs"
$LogFile = Join-Path $LogsDir "service.log"
$Port = 8080
$BindHost = "0.0.0.0"

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $TlsDir | Out-Null

$Index = Join-Path $Frontend "index.html"
if (-not (Test-Path $Index)) {
    throw "Runtime frontend missing at $Index. Run .\scripts\publish_runtime.ps1 first."
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Project venv not found at $Python. Create .venv and pip install -r requirements.txt."
}

& $Python -m pip install -q "cryptography>=42.0.0"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install runtime Python dependencies"
}

$tlsOut = & $Python (Join-Path $Scripts "ensure_lan_tls.py") --dir $TlsDir
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create LAN TLS certificate in $TlsDir"
}
$certPath = ($tlsOut | Select-Object -First 1).ToString().Trim()
$keyPath = ($tlsOut | Select-Object -Skip 1 -First 1).ToString().Trim()
if (-not (Test-Path $certPath) -or -not (Test-Path $keyPath)) {
    throw "LAN TLS certificate files were not created in $TlsDir"
}

$env:PYTHONPATH = "$Backend;$Scripts;$Collection"
$env:MTG_FRONTEND_DIST = $Frontend
# Logging goes through process stdout/stderr redirect below. Do not also set
# MTG_LOG_FILE — Windows will deny a second open of the same log path.

Set-Location $Backend

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $LogFile -Value "`n==== LAN runtime start $timestamp ===="

# cmd redirection avoids PowerShell treating uvicorn stderr INFO as terminating errors.
$argList = @(
    "-m", "uvicorn", "api.main:app",
    "--host", $BindHost,
    "--port", "$Port",
    "--ssl-certfile", $certPath,
    "--ssl-keyfile", $keyPath
)
$argString = ($argList | ForEach-Object {
    if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
}) -join " "

$cmd = "`"$Python`" $argString >> `"$LogFile`" 2>&1"
cmd.exe /c $cmd
exit $LASTEXITCODE
