# Opens the USB stick dialog of the exporter on the interactive desktop (test VMs only) and closes it after 4 minutes.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
. (Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) 'WinDoesNotStick.ps1')
$owner = New-Object System.Windows.Forms.Form
$owner.Text = 'owner'; $owner.WindowState = 'Minimized'; $owner.ShowInTaskbar = $false
$closer = New-Object System.Windows.Forms.Timer; $closer.Interval = 240000
$closer.Add_Tick({ [System.Windows.Forms.Application]::Exit() })
$owner.Add_Shown({ $closer.Start(); try { Show-WdnStickDialog ([System.Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName -eq 'de') $owner } catch { $_.Exception.Message | Out-File C:\wdn-test\stick-dialog-error.txt } })
[System.Windows.Forms.Application]::Run($owner)
