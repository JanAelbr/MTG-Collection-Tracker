# Run the daily price update (legacy HTML reports are optional; use run_app.ps1 for the web app).
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python (Join-Path $Root "scripts\update_prices_report.py")
exit $LASTEXITCODE
