Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = if (Test-Path (Join-Path $PSScriptRoot "scheduler.py")) { $PSScriptRoot } else { Split-Path -Parent $PSScriptRoot }
Set-Location $ProjectRoot

$logDir = Join-Path $ProjectRoot "data\logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = Join-Path $logDir "scheduler_startup.log"

$pyvenv = Join-Path $ProjectRoot ".venv\pyvenv.cfg"
if (-not (Test-Path $pyvenv)) {
    throw "Project virtual environment config not found: $pyvenv"
}

$homeLine = Get-Content $pyvenv | Where-Object { $_ -like "home = *" } | Select-Object -First 1
if (-not $homeLine) {
    throw "Could not find 'home = ...' in $pyvenv"
}

$pythonHome = ($homeLine -split "=", 2)[1].Trim()
$pythonwExe = Join-Path $pythonHome "pythonw.exe"
if (-not (Test-Path $pythonwExe)) {
    throw "Base Python not found: $pythonwExe"
}

$existingProcess = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and
        $_.CommandLine -like "*bootstrap_scheduler_background.py*"
    } |
    Select-Object -First 1

if ($existingProcess) {
    Add-Content -Path $logFile -Value "[$((Get-Date).ToString('s'))] Scheduler already running. PID=$($existingProcess.ProcessId)"
    exit 0
}

Add-Content -Path $logFile -Value "[$((Get-Date).ToString('s'))] Starting scheduler from Windows startup."

Start-Process -FilePath $pythonwExe `
    -ArgumentList (Join-Path $PSScriptRoot "bootstrap_scheduler_background.py") `
    -WindowStyle Hidden
