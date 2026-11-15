# WinDoesNot Setup companion. Compatible with Windows PowerShell 2.0 / .NET 3.5+
# Supports Windows 7, 8, 8.1, 10 and 11. Run elevated to write to the system-drive root.
param(
    # Unattended mode (no window): WinDoesNotSetup.cmd -Unattended -ProfileName NAME -Folders Documents,Pictures
    [switch]$Unattended,
    [string]$ProfileName = '',
    [string]$Folders = 'Documents,Pictures,Music,Videos,Downloads,Desktop',
    [string]$Output = '',
    [switch]$IncludeWifi,
    [string]$Log = ''
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Json-String([string]$value) {
    if ($null -eq $value) { return '""' }
    $result = New-Object System.Text.StringBuilder
    [void]$result.Append('"')
    foreach ($c in $value.ToCharArray()) {
        $n = [int]$c
        if ($n -eq 34) { [void]$result.Append('\"') }
        elseif ($n -eq 92) { [void]$result.Append('\\') }
        elseif ($n -lt 32) { [void]$result.Append(('\u{0:x4}' -f $n)) }
        else { [void]$result.Append($c) }
    }
    [void]$result.Append('"')
    return $result.ToString()
}
function New-HandoffItem([string]$name, [string]$kind) {
    # Keep the real profile name separate from the display label: names can
    # contain the label separator, so splitting display text loses data.
    return New-Object PSObject -Property @{ Name = $name; Kind = $kind; Label = ($name + '  —  ' + $kind) }
}
function Test-PlainDirectory([string]$path) {
    try {
        $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        return $item.PSIsContainer -and (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0)
    } catch { return $false }
}
function Get-WindowsLabel {
    $os = Get-WmiObject Win32_OperatingSystem
    $v = [version]$os.Version
    if ($v.Major -eq 6 -and $v.Minor -eq 1) { return 'Windows 7' }
    if ($v.Major -eq 6 -and $v.Minor -eq 2) { return 'Windows 8' }
    if ($v.Major -eq 6 -and $v.Minor -eq 3) { return 'Windows 8.1' }
    if ($v.Major -ge 10 -and [int]$os.BuildNumber -ge 22000) { return 'Windows 11 ' + $os.BuildNumber }
    if ($v.Major -ge 10) { return 'Windows 10 ' + $os.BuildNumber }
    throw 'Unterstützt werden Windows 7 bis Windows 11.'
}
function Is-Administrator {
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object -TypeName System.Security.Principal.WindowsPrincipal -ArgumentList $id
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}
function Get-WlanName([string]$path) {
    try {
        [xml]$document = [System.IO.File]::ReadAllText($path)
        $node = $document.SelectSingleNode("//*[local-name()='name']")
        if ($node) { return [string]$node.InnerText }
    } catch { }
    return ''
}

function Save-Handoff($selected, [bool]$includeWifi, [string]$root, [string]$windowsLabel) {
    $pending = $root + '.pending-' + [Guid]::NewGuid().ToString('N')
    $backup = $root + '.previous-' + [Guid]::NewGuid().ToString('N')
    $movedPrevious = $false
    $published = $false
    try {
        # Exports can contain clear-text WLAN keys. Keep the entire staging
        # tree accessible only to elevated administrators and SYSTEM.
        $acl = New-Object System.Security.AccessControl.DirectorySecurity
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($sidText in @('S-1-5-18', 'S-1-5-32-544')) {
            $sid = New-Object System.Security.Principal.SecurityIdentifier($sidText)
            $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
            $acl.AddAccessRule($rule)
        }
        [void][System.IO.Directory]::CreateDirectory($pending, $acl)
        $profilesJson = @()
        foreach ($name in ($selected.Keys | Sort-Object)) {
            $items = @($selected[$name] | ForEach-Object { Json-String $_ }) -join ','
            $profilesJson += (Json-String $name) + ':[' + $items + ']'
        }
        $wlanDir = Join-Path $pending 'wlan'
        if ($includeWifi) {
            New-Item -ItemType Directory -Force -Path $wlanDir | Out-Null
            $export = Join-Path $pending ('.wlan-export-' + [Guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Force -Path $export | Out-Null
            try {
                & netsh.exe wlan export profile key=clear folder="$export" | Out-Null
                if ($LASTEXITCODE -ne 0) { throw 'WLAN-Export fehlgeschlagen.' }
                $knownNames = @{}
                Get-ChildItem $wlanDir -Filter 'WLAN-*.xml' -ErrorAction SilentlyContinue | ForEach-Object {
                    $known = Get-WlanName $_.FullName
                    if ($known) { $knownNames[$known] = $true }
                }
                $i = 0
                Get-ChildItem $wlanDir -Filter 'WLAN-*.xml' -ErrorAction SilentlyContinue | ForEach-Object {
                    if ($_.BaseName -match '^WLAN-(\d+)$' -and [int]$matches[1] -gt $i) { $i = [int]$matches[1] }
                }
                $validExports = 0
                Get-ChildItem $export -Filter '*.xml' | ForEach-Object {
                    $network = Get-WlanName $_.FullName
                    if ($network) {
                        $validExports++
                        if (-not $knownNames.ContainsKey($network)) {
                            $i++; $knownNames[$network] = $true
                            Copy-Item $_.FullName (Join-Path $wlanDir ('WLAN-{0:D3}.xml' -f $i))
                        }
                    }
                }
                if ((Get-ChildItem $export -Filter '*.xml' | Measure-Object).Count -eq 0) { throw 'Windows hat keine WLAN-Profile exportiert.' }
                if ($validExports -eq 0) { throw 'Die WLAN-Profile konnten nicht gelesen werden.' }
            } finally {
                Remove-Item $export -Recurse -Force -ErrorAction Stop
            }
        }
        $culture = [System.Globalization.CultureInfo]::CurrentCulture.Name.Replace('-', '_')
        if ($culture -notmatch '^[A-Za-z]{2,3}(_[A-Za-z]{2})?$') { $culture = 'en_US' }
        $manifest = '{"schema":1,"windows_version":' + (Json-String $windowsLabel) + ',"locale":' + (Json-String $culture) + ',"profiles":{' + ($profilesJson -join ',') + '},"wlan":' + $includeWifi.ToString().ToLowerInvariant() + '}'
        $utf8 = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
        $bytes = $utf8.GetBytes($manifest)
        if ($bytes.Length -gt 65536) { throw 'Die Auswahl ist zu groß.' }
        [System.IO.File]::WriteAllBytes((Join-Path $pending 'manifest.json'), $bytes)
        if ([System.IO.Directory]::Exists($root)) {
            $existing = New-Object System.IO.DirectoryInfo($root)
            if (($existing.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Der vorhandene Übergabeordner ist eine Verknüpfung.' }
            # Refuse to delete unrelated user-added files from an older handoff.
            foreach ($entry in $existing.GetFileSystemInfos()) {
                if ($entry.Name -ne 'manifest.json' -and $entry.Name -ne 'wlan') { throw 'Der vorhandene Übergabeordner enthält zusätzliche Dateien und wird nicht überschrieben.' }
                if (($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Der vorhandene Übergabeordner enthält eine Verknüpfung.' }
                if ($entry.Name -eq 'wlan') {
                    if (-not ($entry -is [System.IO.DirectoryInfo])) { throw 'Ungültiger WLAN-Ordner.' }
                    foreach ($file in $entry.GetFileSystemInfos()) {
                        if (($file.Attributes -band ([System.IO.FileAttributes]::Directory -bor [System.IO.FileAttributes]::ReparsePoint)) -ne 0 -or $file.Name -notlike 'WLAN-*.xml') { throw 'Der WLAN-Ordner enthält zusätzliche Dateien und wird nicht überschrieben.' }
                    }
                }
            }
            [System.IO.Directory]::Move($root, $backup)
            $movedPrevious = $true
        }
        try {
            [System.IO.Directory]::Move($pending, $root)
            $published = $true
        } catch {
            if ($movedPrevious) {
                [System.IO.Directory]::Move($backup, $root)
                $movedPrevious = $false
            }
            throw
        }
        if ($movedPrevious) {
            [System.IO.Directory]::Delete($backup, $true)
            $movedPrevious = $false
        }
    } catch {
        $message = $_.Exception.Message
        if ($published -and $movedPrevious) {
            $message = 'Die neue Auswahl wurde gespeichert, aber der vorherige Übergabeordner konnte nicht gelöscht werden: ' + $backup + '. Er kann alte WLAN-Schlüssel enthalten.'
        }
        throw (New-Object System.Exception($message))
    } finally {
        if ([System.IO.Directory]::Exists($pending)) {
            try { [System.IO.Directory]::Delete($pending, $true) } catch { }
        }
    }
}
function Get-HandoffItems([string]$usersRoot, [string[]]$folders) {
    $items = New-Object System.Collections.ArrayList
    if (-not (Test-PlainDirectory $usersRoot)) { return $items }
    Get-ChildItem $usersRoot | Where-Object { $_.PSIsContainer -and ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0 -and @('Public','Default','Default User','All Users') -notcontains $_.Name } | Sort-Object Name | ForEach-Object {
        $profile = $_
        foreach ($folder in $folders) {
            $path = Join-Path $profile.FullName $folder
            # The Linux reader reconstructs canonical Windows paths only.
            if (-not (Test-PlainDirectory $path)) { continue }
            [void]$items.Add((New-HandoffItem $profile.Name $folder))
        }
        $firefoxPath = $profile.FullName
        $firefoxSafe = $true
        foreach ($component in @('AppData','Roaming','Mozilla','Firefox')) {
            $firefoxPath = Join-Path $firefoxPath $component
            if (-not (Test-PlainDirectory $firefoxPath)) { $firefoxSafe = $false; break }
        }
        $firefoxIni = Join-Path $firefoxPath 'profiles.ini'
        if ($firefoxSafe -and (Test-Path -LiteralPath $firefoxIni -PathType Leaf)) {
            [void]$items.Add((New-HandoffItem $profile.Name 'Firefox'))
        }
    }
    return $items
}
function Group-Selection($entries) {
    $selected = @{}
    foreach ($entry in $entries) {
        $name = [string]$entry.Name
        $folder = [string]$entry.Kind
        if (-not $selected.ContainsKey($name)) { $selected[$name] = New-Object System.Collections.ArrayList }
        [void]$selected[$name].Add($folder)
    }
    return $selected
}
function Write-SetupLog([string]$line) {
    if (-not $script:LogPath) { return }
    try { [System.IO.File]::AppendAllText($script:LogPath, ((Get-Date).ToString('s') + ' ' + $line + "`r`n")) } catch { }
}
$isGerman = [System.Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName -eq 'de'
try { $windowsLabel = Get-WindowsLabel } catch {
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'WinDoesNot Setup') | Out-Null
    exit 1
}
if (-not (Is-Administrator)) {
    if ($Unattended) { exit 3 }
    if ($isGerman) { $adminText = 'Zum Schreiben der Auswahl auf das Windows-Laufwerk ist eine Administratorfreigabe nötig. Es werden keine Windows-Anmeldepasswörter ausgelesen.' }
    else { $adminText = 'Administrator permission is required to write the selection to the Windows drive. Windows sign-in passwords are not read.' }
    $answer = [System.Windows.Forms.MessageBox]::Show($adminText, 'WinDoesNot Setup', 'OKCancel', 'Information')
    if ($answer -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',('"' + $MyInvocation.MyCommand.Path + '"'))
    exit 0
}

$root = $env:SystemDrive + '\WinDoesNotHandoff'
if ($Output) { $root = $Output.TrimEnd('\') }
$script:LogPath = $null
if ($Unattended) {
    $script:LogPath = $Log
    if (-not $script:LogPath) { $script:LogPath = $root + '-unattended.log' }
}
$usersRoot = Join-Path $env:SystemDrive 'Users'
$defaultFolders = @('Documents','Pictures','Music','Videos','Downloads','Desktop')

if ($Unattended) {
    # No window, no prompts. Exit codes: 0 ok, 2 invalid input or nothing selected, 3 write or permission error.
    Write-SetupLog ('start ' + $windowsLabel)
    try {
        $wanted = @($Folders -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        if ($wanted.Count -eq 0) { Write-SetupLog 'error: no folders'; exit 2 }
        $who = $ProfileName
        if (-not $who) { $who = $env:USERNAME }
        $found = @(Get-HandoffItems $usersRoot $wanted)
        Write-SetupLog ('users root ' + $usersRoot + ', folders wanted ' + ($wanted -join ',') + ', items found ' + $found.Count)
        $picked = @($found | Where-Object { ($who -eq '*' -or $_.Name -eq $who) -and ($_.Kind -ne 'Firefox' -or $wanted -contains 'Firefox') })
        $pickedCount = ($picked | Measure-Object).Count
        if ($pickedCount -eq 0) { Write-SetupLog ('error: nothing to export for profile ' + $who); exit 2 }
        $selected = Group-Selection $picked
        Save-Handoff $selected ([bool]$IncludeWifi) $root $windowsLabel
        Write-SetupLog ('ok: ' + $pickedCount + ' items, wlan ' + [bool]$IncludeWifi)
        exit 0
    } catch {
        Write-SetupLog ('error: ' + $_.Exception.Message)
        exit 3
    }
}
# Show 'Windows 10', not the build number, in the window.
$shownLabel = $windowsLabel -replace '^(Windows [0-9.]+).*$','$1'
$form = New-Object System.Windows.Forms.Form
if ($isGerman) { $form.Text = 'WinDoesNot Setup - Daten für den Umzug auswählen' }
else { $form.Text = 'WinDoesNot Setup - Select data to migrate' }
# Design coordinates are at 96 DPI; WinForms scales controls and the scroll area together.
$form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
$form.AutoScaleDimensions = New-Object -TypeName System.Drawing.SizeF -ArgumentList 96,96
$form.ClientSize = New-Object -TypeName System.Drawing.Size -ArgumentList 700,680
$form.AutoScroll = $true
$form.AutoScrollMinSize = New-Object -TypeName System.Drawing.Size -ArgumentList 700,680
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$form.BackColor = [System.Drawing.Color]::FromArgb(27,27,31)
$form.ForeColor = [System.Drawing.Color]::FromArgb(238,238,238)
$fontName = 'Tahoma'
$installedFonts = New-Object System.Drawing.Text.InstalledFontCollection
foreach ($family in $installedFonts.Families) { if ($family.Name -eq 'Segoe UI') { $fontName = 'Segoe UI'; break } }
$fontFamily = New-Object System.Drawing.FontFamily($fontName)
$installedFonts.Dispose()
$form.Font = New-Object System.Drawing.Font($fontFamily, 9.5, [System.Drawing.FontStyle]::Regular)
$title = New-Object System.Windows.Forms.Label
$title.Text = 'WinDoesNot. Setup'
$title.Font = New-Object System.Drawing.Font($fontFamily, 19, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(254,111,45)
$title.AutoSize = $false
$title.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,16
$title.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,42
$form.Controls.Add($title)
$intro = New-Object System.Windows.Forms.Label
if ($isGerman) { $intro.Text = "Quelle: $shownLabel`r`nWähle die Ordner für deinen Umzug. Deine Dateien bleiben an ihrem ursprünglichen Ort. Browser-Passwörter werden nicht automatisch ausgelesen." }
else { $intro.Text = "Source: $shownLabel`r`nChoose the folders to migrate. Your files stay in their original location. Browser passwords are not read automatically." }
$intro.AutoSize = $false
$intro.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,66
$intro.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,70
$form.Controls.Add($intro)
$list = New-Object System.Windows.Forms.CheckedListBox
$list.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,142
$list.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,350
$list.IntegralHeight = $false
$list.CheckOnClick = $true
$list.DisplayMember = 'Label'
$list.BackColor = [System.Drawing.Color]::FromArgb(20,20,20)
$list.ForeColor = [System.Drawing.Color]::FromArgb(238,238,238)
$list.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
foreach ($item in @(Get-HandoffItems $usersRoot $defaultFolders)) {
    $idx = $list.Items.Add($item)
    if ($item.Name -eq $env:USERNAME) { $list.SetItemChecked($idx, $true) }
}
$form.Controls.Add($list)
$wifi = New-Object System.Windows.Forms.CheckBox
if ($isGerman) { $wifi.Text = 'Gespeicherte WLAN-Schlüssel exportieren (lesbar auf dem USB/Laufwerk gespeichert)' }
else { $wifi.Text = 'Export saved Wi-Fi keys (stored in readable form on the USB drive)' }
$wifi.AutoSize = $false
$wifi.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$wifi.BackColor = [System.Drawing.Color]::FromArgb(27,27,31)
$wifi.ForeColor = [System.Drawing.Color]::FromArgb(238,238,238)
$wifi.UseVisualStyleBackColor = $false
$wifi.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,508
$wifi.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,40
$form.Controls.Add($wifi)
$notice = New-Object System.Windows.Forms.Label
if ($isGerman) { $notice.Text = 'Umgeleitete und nicht lokal verfügbare Ordner fehlen möglicherweise. Chrome/Edge-Passwörter im jeweiligen Browser als CSV exportieren. Firefox schließen; Passwortübernahme ist ungeprüft.' }
else { $notice.Text = 'Redirected folders and folders unavailable locally may be missing. Export Chrome/Edge passwords as CSV in the browser. Close Firefox; password import is unverified.' }
$notice.AutoSize = $false
$notice.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,552
$notice.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,62
$form.Controls.Add($notice)
$save = New-Object System.Windows.Forms.Button
if ($isGerman) { $save.Text = 'Auswahl speichern' } else { $save.Text = 'Save selection' }
$save.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 510,630
$save.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 164,34
$save.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$save.FlatAppearance.BorderSize = 1
$save.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(254,111,45)
$save.FlatAppearance.MouseOverBackColor = [System.Drawing.Color]::FromArgb(255,145,88)
$save.FlatAppearance.MouseDownBackColor = [System.Drawing.Color]::FromArgb(220,85,25)
$save.BackColor = [System.Drawing.Color]::FromArgb(254,111,45)
$save.ForeColor = [System.Drawing.Color]::FromArgb(20,20,20)
$save.UseVisualStyleBackColor = $false
# Clamp the scaled outer size, including the native frame, after WinForms has scaled the layout.
$form.Add_Load({
    $graphics = $form.CreateGraphics()
    try { $dpiFactor = $graphics.DpiX / 96.0 } finally { $graphics.Dispose() }
    $workArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $scaledWidth = [int][Math]::Ceiling(700 * $dpiFactor)
    $wanted = [int][Math]::Ceiling(680 * $dpiFactor)
    # Start from the design size, then fit the window to the work area and measure what is left of the client area.
    $form.ClientSize = New-Object -TypeName System.Drawing.Size -ArgumentList $scaledWidth,$wanted
    $width = [Math]::Min($form.Width, $workArea.Width)
    $height = [Math]::Min($form.Height, $workArea.Height)
    $form.Size = New-Object -TypeName System.Drawing.Size -ArgumentList $width,$height
    $missing = $wanted - $form.ClientSize.Height
    # Small screens (800x600): shrink the list so that the Save button stays visible without scrolling.
    $shrink = 0
    if ($missing -gt 0) { $shrink = [Math]::Min($missing, $list.Height - [int](90 * $dpiFactor)) }
    if ($shrink -gt 0) {
        $list.Height = $list.Height - $shrink
        foreach ($moved in @($wifi, $notice, $save)) { $moved.Top = $moved.Top - $shrink }
    }
    if ($shrink -ge $missing) { $form.AutoScroll = $false }
    else { $form.AutoScrollMinSize = New-Object -TypeName System.Drawing.Size -ArgumentList $scaledWidth,($wanted - $shrink) }
    $left = $workArea.Left + [int](($workArea.Width - $width) / 2)
    $top = $workArea.Top + [int](($workArea.Height - $height) / 2)
    $form.Location = New-Object -TypeName System.Drawing.Point -ArgumentList $left,$top
})
$save.Add_Click({
    try {
        Save-Handoff (Group-Selection $list.CheckedItems) $wifi.Checked $root $windowsLabel
        if ([System.Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName -eq 'de') {
            $next = "Auswahl gespeichert unter $root`r`n`r`n1. Windows neu starten, nicht herunterfahren.`r`n2. WinDoesNot-USB-Stick einstecken und davon starten.`r`n3. Im Installer 'Parallel installieren' wählen. Dort erscheint die Seite Windows-Daten.`r`n4. Daten übernehmen.`r`n`r`nFalls gewählt, liegen WLAN-Schlüssel im Übergabeordner im Klartext."
        } else {
            $next = "Selection saved at $root`r`n`r`n1. Restart Windows; do not shut it down.`r`n2. Insert the WinDoesNot USB stick and boot from it.`r`n3. In the installer choose Install alongside. The Windows data page appears there.`r`n4. Import your data.`r`n`r`nIf selected, WLAN keys are stored in clear text in the handoff folder."
        }
        [System.Windows.Forms.MessageBox]::Show($next, 'WinDoesNot Setup') | Out-Null
        $form.Close()
    } catch {
        if ($isGerman) { $errorTitle = 'WinDoesNot Setup - Fehler' } else { $errorTitle = 'WinDoesNot Setup - Error' }
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, $errorTitle, 'OK', 'Error') | Out-Null
    }
})
$form.Controls.Add($save)
[void]$form.ShowDialog()
