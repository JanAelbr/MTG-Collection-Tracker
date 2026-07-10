# Run collection API performance benchmarks (search + set filter).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "Running performance benchmarks..."
py -3 -m unittest tests.test_performance_benchmarks -v 2>&1
