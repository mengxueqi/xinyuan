Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = if (Test-Path (Join-Path $PSScriptRoot "ui_app.py")) { $PSScriptRoot } else { Split-Path -Parent $PSScriptRoot }
Set-Location $ProjectRoot

function Test-PortInUse {
    param(
        [string]$Address = "localhost",
        [int]$Port = 8501
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($Address, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(1000, $false)
        if (-not $connected) {
            return $false
        }
        $client.EndConnect($async) | Out-Null
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Get-PortOwningProcessId {
    param(
        [int]$Port = 8501
    )

    $netstatLines = netstat -ano | Select-String ":$Port"
    foreach ($line in $netstatLines) {
        $parts = ($line.ToString() -split '\s+') | Where-Object { $_ }
        if ($parts.Length -ge 5 -and $parts[0] -eq 'TCP' -and $parts[1] -match ":$Port$" -and $parts[3] -eq 'LISTENING') {
            return [int]$parts[4]
        }
    }
    return $null
}

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
$pythonwExe = Join-Path $pythonHome "pythonw.exe"
if (Test-Path $pythonwExe) {
    $pythonRunner = $pythonwExe
}
elseif (Test-Path $pythonExe) {
    $pythonRunner = $pythonExe
}
else {
    throw "Base Python not found under: $pythonHome"
}

$existingPid = Get-PortOwningProcessId -Port 8501
$hadExistingProcess = $null -ne $existingPid
if ($existingPid) {
    try {
        Stop-Process -Id $existingPid -Force -ErrorAction Stop
        Start-Sleep -Seconds 2
    }
    catch {
        throw "Existing UI process on port 8501 could not be stopped (PID: $existingPid)."
    }
}

$bootstrapPath = Join-Path $PSScriptRoot "bootstrap_ui.py"
$process = Start-Process -FilePath $pythonRunner -ArgumentList "`"$bootstrapPath`"" -WindowStyle Hidden -PassThru

$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-PortInUse -Address "localhost" -Port 8501) {
        $ready = $true
        break
    }
    if ($process.HasExited) {
        throw "UI process exited before port 8501 became ready."
    }
}

if (-not $ready) {
    throw "UI server did not become ready on port 8501 in time."
}

if (-not $hadExistingProcess) {
    Start-Process "http://localhost:8501"
}
