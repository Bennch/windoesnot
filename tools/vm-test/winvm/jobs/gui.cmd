@echo off
rem Interactive logon task (elevated): opens the exporter window for screenshots. Disposable test VMs only.
if not exist "%~dp0WDN_GUI.txt" goto :eof
set RES=
for %%d in (D E F G H I J K L M N) do if exist %%d:\WDN_RESULTS.txt set RES=%%d:
ping -n 20 127.0.0.1 >nul
xcopy /E /Y /I "%~dp0windows" C:\wdn-test\windows >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue 'C:\Users\wdnsmoke','C:\Users\Test User'; Get-ChildItem C:\Users | Where-Object { $_.Name -like 'Ad*ller' } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Recurse -Force -ErrorAction SilentlyContinue 'C:\WinDoesNotHandoff'"
for %%f in (Documents Pictures Music Videos Downloads Desktop) do if not exist C:\Users\Anna\%%f mkdir C:\Users\Anna\%%f
set USERNAME=Anna
start "" /min powershell.exe -WindowStyle Hidden -NoProfile -STA -ExecutionPolicy Bypass -File C:\wdn-test\windows\WinDoesNotSetup.ps1
if not "%RES%"=="" echo started > %RES%\gui-started.txt
