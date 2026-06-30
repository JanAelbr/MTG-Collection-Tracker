# Register a Windows Scheduled Task to run the daily price update at 08:00.
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Runner = Join-Path $Root "scripts\run_daily_update.ps1"
$TaskName = "MtgCollectionDailyUpdate"

if (-not (Test-Path $Runner)) {
    Write-Error "Runner script not found: $Runner"
}

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`""
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Update MTG collection prices for the interactive web app." `
    -Force

Write-Host "Scheduled task registered: $TaskName (daily at 08:00)"
Write-Host "Runner: $Runner"
