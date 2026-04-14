Set shell = CreateObject("WScript.Shell")
shell.Run "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""D:\codex\xinyuan\start_ui.ps1""", 0, False
Set shell = Nothing
