@echo off
setlocal
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0WinDoesNotSetup.ps1" %*
endlocal
