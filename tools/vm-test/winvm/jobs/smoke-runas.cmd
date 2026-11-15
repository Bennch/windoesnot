@echo off
rem Wait (up to about 3 minutes) for the results disk: USB drives appear after the boot task starts.
set TRIES=0
:findres
set RES=
for %%d in (D E F G H I J K L M N) do if exist %%d:\WDN_RESULTS.txt set RES=%%d:
if not "%RES%"=="" goto found
set /a TRIES+=1
if %TRIES% GEQ 60 goto :eof
ping -n 4 127.0.0.1 >nul
goto findres
:found
set PAY=%~dp0
if exist %RES%\DONE.txt del %RES%\DONE.txt
xcopy /E /Y /I "%PAY%windows" C:\wdn-test\windows >nul
ver > %RES%\ver.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList '-NoProfile','-STA','-ExecutionPolicy','Bypass','-File','C:\wdn-test\windows\tests\vm-smoke.ps1','-ResultsDir','%RES%\'; exit $p.ExitCode" > %RES%\smoke-console.txt 2>&1
echo %ERRORLEVEL% > %RES%\smoke-exit.txt
echo DONE > %RES%\DONE.txt
