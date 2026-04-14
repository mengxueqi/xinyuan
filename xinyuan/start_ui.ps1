Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

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

$pyvenv = Join-Path $PSScriptRoot ".venv\pyvenv.cfg"
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

if (Test-PortInUse -Address "localhost" -Port 8501) {
    Start-Process "http://localhost:8501"
    exit 0
}

Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8501'"
& $pythonExe ".\bootstrap_ui.py"
