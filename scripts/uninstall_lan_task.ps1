# Remove LAN runtime auto-start (scheduled task and/or Startup-folder launcher).
$ErrorActionPreference = "Continue"

$TaskName = "MtgCollectionTrackerLan"
$StartupCmd = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\MtgCollectionTrackerLan.cmd"
$removed = $false

& schtasks.exe /End /TN $TaskName 2>$null | Out-Null
& schtasks.exe /Delete /TN $TaskName /F 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removed scheduled task '$TaskName'."
    $removed = $true
}
else {
    Write-Warning "Could not remove scheduled task '$TaskName' (may need elevation):"
    Write-Warning "  schtasks /Delete /TN $TaskName /F"
}

if (Test-Path $StartupCmd) {
    Remove-Item -Force $StartupCmd
    Write-Host "Removed Startup launcher: $StartupCmd"
    $removed = $true
}

if (-not $removed) {
    Write-Host "Nothing removed. If the old At-startup task remains, delete it from an elevated PowerShell."
}
