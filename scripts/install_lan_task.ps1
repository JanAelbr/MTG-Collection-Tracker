# Install LAN runtime auto-start for the current user.
# Prefers Task Scheduler (At logon). Falls back to the user Startup folder
# when Task Scheduler is access-denied (common without elevation).
$ErrorActionPreference = "Stop"

$TaskName = "MtgCollectionTrackerLan"
$Root = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $PSScriptRoot "start_lan_runtime.ps1"
$FrontendIndex = Join-Path $Root "runtime\frontend\index.html"
$StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$StartupCmd = Join-Path $StartupDir "MtgCollectionTrackerLan.cmd"

if (-not (Test-Path $StartScript)) {
    throw "Missing start script: $StartScript"
}
if (-not (Test-Path $FrontendIndex)) {
    throw "Runtime frontend missing. Run .\scripts\publish_runtime.ps1 first."
}

$tr = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`""
$installed = $false

# --- Try Task Scheduler (At logon) ---
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$deleteOut = & schtasks.exe /Delete /TN $TaskName /F 2>&1
$ErrorActionPreference = $prev

$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$createOut = & schtasks.exe /Create /TN $TaskName /TR $tr /SC ONLOGON /RL LIMITED /F 2>&1
$createCode = $LASTEXITCODE
$ErrorActionPreference = $prev

if ($createCode -eq 0) {
    $installed = $true
    Write-Host "Registered scheduled task '$TaskName' (At logon)."
    Write-Host "Start now:  schtasks /Run /TN $TaskName"
}
else {
    Write-Warning "Task Scheduler registration failed (often needs elevation to replace an old At-startup task):"
    Write-Warning (($createOut | Out-String).Trim())
}

# --- Fallback: per-user Startup folder (no admin) ---
if (-not $installed) {
    New-Item -ItemType Directory -Force -Path $StartupDir | Out-Null
    $cmdLines = @(
        "@echo off"
        "rem Auto-start MTG Collection Tracker LAN runtime (HTTPS :8080)"
        "start `"`" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`""
    )
    Set-Content -Path $StartupCmd -Value $cmdLines -Encoding ASCII
    $installed = $true
    Write-Host "Installed Startup-folder launcher:"
    Write-Host "  $StartupCmd"
    Write-Host "This runs at your Windows logon (no admin required)."
    Write-Host "Optional (elevated PowerShell) to clean the old broken task:"
    Write-Host "  schtasks /Delete /TN $TaskName /F"
}

Write-Host "Start now:  .\scripts\start_lan_runtime.ps1"
Write-Host "Remove:     .\scripts\uninstall_lan_task.ps1"
Write-Host "Open:       https://127.0.0.1:8080  or  https://<lan-ip>:8080"
Write-Host "Accept the self-signed certificate warning once."
Write-Host "If devices cannot connect, allow Windows Firewall inbound TCP 8080."
