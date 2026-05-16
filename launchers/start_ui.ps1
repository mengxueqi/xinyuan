Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$UiPort = 8510
$ProjectRoot = if (Test-Path (Join-Path $PSScriptRoot "ui_app.py")) { $PSScriptRoot } else { Split-Path -Parent $PSScriptRoot }
Set-Location $ProjectRoot

function Test-PortInUse {
    param(
        [string]$Address = "localhost",
        [int]$Port = $UiPort
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
        [int]$Port = $UiPort
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

$streamlitExe = Join-Path $ProjectRoot ".venv\Scripts\streamlit.exe"
if (-not (Test-Path $streamlitExe)) {
    throw "Project Streamlit executable not found: $streamlitExe"
}

$existingPid = Get-PortOwningProcessId -Port $UiPort
if ($existingPid) {
    Start-Process "http://localhost:$UiPort"
    exit 0
}

$uiScript = Join-Path $ProjectRoot "ui_app.py"
$streamlitArgs = @(
    "run",
    "`"$uiScript`"",
    "--server.address", "localhost",
    "--server.port", "$UiPort",
    "--server.headless", "true",
    "--browser.gatherUsageStats", "false"
)
$process = Start-Process -FilePath $streamlitExe -ArgumentList $streamlitArgs -WindowStyle Hidden -PassThru

$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-PortInUse -Address "localhost" -Port $UiPort) {
        $ready = $true
        break
    }
    if ($process.HasExited) {
        throw "UI process exited before port $UiPort became ready."
    }
}

if (-not $ready) {
    throw "UI server did not become ready on port $UiPort in time."
}

Start-Process "http://localhost:$UiPort"
