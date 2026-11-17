@echo off
set RES=
for %%d in (D E F G H I J K L M N O P) do if exist %%d:\WDN_RESULTS.txt set RES=%%d:
set TRIES=0
:wait
if not "%RES%"=="" goto go
set /a TRIES+=1
if %TRIES% GEQ 60 goto :eof
ping -n 4 127.0.0.1 >nul
for %%d in (D E F G H I J K L M N O P) do if exist %%d:\WDN_RESULTS.txt set RES=%%d:
goto wait
:go
set PAY=%~dp0
if exist %RES%\DONE.txt goto :eof
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','%PAY%usb-run.ps1','-Res','%RES%','-Pay','%PAY:~0,-1%'; exit $p.ExitCode"
