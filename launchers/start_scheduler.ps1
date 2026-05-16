Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = if (Test-Path (Join-Path $PSScriptRoot "scheduler.py")) { $PSScriptRoot } else { Split-Path -Parent $PSScriptRoot }
Set-Location $ProjectRoot

$pyvenv = Join-Path $ProjectRoot ".venv\pyvenv.cfg"
if (-not (Test-Path $pyvenv)) {
    throw "Project virtual environment config not found: $pyvenv"
}

$homeLine = Get-Content $pyvenv | Where-Object { $_ -like "home = *" } | Select-Object -First 1
if (-not $homeLine) {
    throw "Could not find 'home = ...' in $pyvenv"
}

$pythonHome = ($homeLine -split "=", 2)[1].Trim()
$pythonExe = Join-Path $pythonHome "python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Base Python not found: $pythonExe"
}

& $pythonExe (Join-Path $PSScriptRoot "bootstrap_scheduler.py")
