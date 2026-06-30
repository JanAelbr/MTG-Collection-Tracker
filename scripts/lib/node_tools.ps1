function Ensure-NodePath {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        return
    }

    $candidates = @(
        (Join-Path $env:ProgramFiles "nodejs"),
        (Join-Path $env:LOCALAPPDATA "Programs\node")
    )

    foreach ($dir in $candidates) {
        $npm = Join-Path $dir "npm.cmd"
        if (Test-Path $npm) {
            $env:PATH = "$dir;$env:PATH"
            return
        }
    }

    throw @"
Node.js/npm was not found on PATH.

Install Node.js from https://nodejs.org/ and restart the terminal, or ensure npm.cmd is available.
Checked:
  - $($candidates -join "`n  - ")
"@
}
