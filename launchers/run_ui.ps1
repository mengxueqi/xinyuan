$ProjectRoot = if (Test-Path (Join-Path $PSScriptRoot "ui_app.py")) { $PSScriptRoot } else { Split-Path -Parent $PSScriptRoot }
Set-Location $ProjectRoot
& ".\.venv\Scripts\python.exe" -m streamlit run ".\ui_app.py"
