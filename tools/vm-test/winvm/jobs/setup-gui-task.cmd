@echo off
rem Creates the interactive elevated logon task WdnGui (needs an elevated process).
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
if exist %RES%\DONE.txt del %RES%\DONE.txt
echo job started > %RES%\job-started.txt
set TASK=schtasks /create /tn WdnGui /sc onlogon /ru tester /rp Test12345 /it /rl highest /f /tr "cmd /c for %%d in (D E F G H I J K L M N) do if exist %%d:\gui.cmd call %%d:\gui.cmd"
net session >nul 2>&1
if not %ERRORLEVEL%==0 goto elevate
%TASK% > %RES%\gui-task.txt 2>&1
goto finish
:elevate
echo schtasks /create /tn WdnGui /sc onlogon /ru tester /rp Test12345 /it /rl highest /f /tr "cmd /c for %%%%d in (D E F G H I J K L M N) do if exist %%%%d:\gui.cmd call %%%%d:\gui.cmd" ^> %RES%\gui-task.txt 2^>^&1 > %RES%\gui-task.cmd
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -Verb RunAs -Wait -ArgumentList '/c','%RES%\gui-task.cmd'"
:finish
echo DONE > %RES%\DONE.txt
