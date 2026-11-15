# WinDoesNot Setup companion. Compatible with Windows PowerShell 2.0 / .NET 3.5+
# Supports Windows 7, 8, 8.1, 10 and 11. Run elevated to write to the system-drive root.
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

try { $windowsLabel = Get-WindowsLabel } catch {
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'WinDoesNot Setup') | Out-Null
    exit 1
}
if (-not (Is-Administrator)) {
    $answer = [System.Windows.Forms.MessageBox]::Show('Zum Schreiben der Auswahl auf das Windows-Laufwerk ist eine Administratorfreigabe nötig. Es werden keine Windows-Anmeldepasswörter ausgelesen.', 'WinDoesNot Setup', 'OKCancel', 'Information')
    if ($answer -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
    Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',('"' + $MyInvocation.MyCommand.Path + '"'))
    exit 0
}

$root = $env:SystemDrive + '\WinDoesNotHandoff'
$usersRoot = Join-Path $env:SystemDrive 'Users'
$folders = @('Documents','Pictures','Music','Videos','Downloads','Desktop')
$form = New-Object System.Windows.Forms.Form
$form.Text = 'WinDoesNot Setup – Daten für den Umzug auswählen'
$form.ClientSize = New-Object -TypeName System.Drawing.Size -ArgumentList 700,650
$form.MinimumSize = New-Object -TypeName System.Drawing.Size -ArgumentList 716,689
$form.StartPosition = 'CenterScreen'
$form.BackColor = [System.Drawing.Color]::FromArgb(25, 25, 34)
$form.ForeColor = [System.Drawing.Color]::FromArgb(240, 240, 245)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$title = New-Object System.Windows.Forms.Label
$title.Text = 'WinDoesNot. Setup'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 19, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(255, 124, 48)
$title.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 22,16
$title.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,42
$form.Controls.Add($title)
$intro = New-Object System.Windows.Forms.Label
$intro.Text = "Quelle: $windowsLabel`r`nWähle die Ordner für deinen Umzug. Deine Dateien bleiben an ihrem ursprünglichen Ort. Browser-Passwörter werden nicht automatisch ausgelesen."
$intro.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,66; $intro.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,60
$form.Controls.Add($intro)
$list = New-Object System.Windows.Forms.CheckedListBox
$list.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,132; $list.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,360
$list.CheckOnClick = $true
$list.DisplayMember = 'Label'
$list.BackColor = [System.Drawing.Color]::FromArgb(38, 38, 48)
$list.ForeColor = [System.Drawing.Color]::FromArgb(240, 240, 245)
$list.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$list.Font = New-Object System.Drawing.Font('Segoe UI', 10)
if (Test-PlainDirectory $usersRoot) {
    Get-ChildItem $usersRoot | Where-Object { $_.PSIsContainer -and ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0 -and @('Public','Default','Default User','All Users') -notcontains $_.Name } | Sort-Object Name | ForEach-Object {
        $profile = $_
        foreach ($folder in $folders) {
            $path = Join-Path $profile.FullName $folder
            # The Linux reader reconstructs canonical Windows paths only.
            if (-not (Test-PlainDirectory $path)) { continue }
            $idx = $list.Items.Add((New-HandoffItem $profile.Name $folder))
            if ($profile.Name -eq $env:USERNAME) { $list.SetItemChecked($idx, $true) }
        }
        $firefoxPath = $profile.FullName
        $firefoxSafe = $true
        foreach ($component in @('AppData','Roaming','Mozilla','Firefox')) {
            $firefoxPath = Join-Path $firefoxPath $component
            if (-not (Test-PlainDirectory $firefoxPath)) { $firefoxSafe = $false; break }
        }
        $firefoxIni = Join-Path $firefoxPath 'profiles.ini'
        if ($firefoxSafe -and (Test-Path -LiteralPath $firefoxIni -PathType Leaf)) {
            $idx = $list.Items.Add((New-HandoffItem $profile.Name 'Firefox'))
            if ($profile.Name -eq $env:USERNAME) { $list.SetItemChecked($idx, $true) }
        }
    }
}
$form.Controls.Add($list)
$wifi = New-Object System.Windows.Forms.CheckBox
$wifi.Text = 'Gespeicherte WLAN-Schlüssel exportieren (lesbar auf dem USB/Laufwerk gespeichert)'
$wifi.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,508; $wifi.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,28
$form.Controls.Add($wifi)
$notice = New-Object System.Windows.Forms.Label
$notice.Text = 'Umgeleitete und nicht lokal verfügbare Ordner fehlen möglicherweise. Chrome/Edge-Passwörter im jeweiligen Browser als CSV exportieren. Firefox schließen; Passwortübernahme ist ungeprüft.'
$notice.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 24,545; $notice.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 650,42
$form.Controls.Add($notice)
$save = New-Object System.Windows.Forms.Button
$save.Text = 'Auswahl speichern'; $save.Location = New-Object -TypeName System.Drawing.Point -ArgumentList 510,602; $save.Size = New-Object -TypeName System.Drawing.Size -ArgumentList 164,34
$save.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$save.FlatAppearance.BorderSize = 0
$save.BackColor = [System.Drawing.Color]::FromArgb(255, 111, 45)
$save.ForeColor = [System.Drawing.Color]::White
$save.UseVisualStyleBackColor = $false
$save.Add_Click({
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
        $selected = @{}
        foreach ($entry in $list.CheckedItems) {
            $name = [string]$entry.Name
            $folder = [string]$entry.Kind
            if (-not $selected.ContainsKey($name)) { $selected[$name] = New-Object System.Collections.ArrayList }
            [void]$selected[$name].Add($folder)
        }
        $profilesJson = @()
        foreach ($name in ($selected.Keys | Sort-Object)) {
            $items = @($selected[$name] | ForEach-Object { Json-String $_ }) -join ','
            $profilesJson += (Json-String $name) + ':[' + $items + ']'
        }
        $wlanDir = Join-Path $pending 'wlan'
        if ($wifi.Checked) {
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
        $manifest = '{"schema":1,"windows_version":' + (Json-String $windowsLabel) + ',"locale":' + (Json-String $culture) + ',"profiles":{' + ($profilesJson -join ',') + '},"wlan":' + $wifi.Checked.ToString().ToLowerInvariant() + '}'
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
        if ([System.Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName -eq 'de') {
            $next = "Auswahl gespeichert unter $root`r`n`r`n1. Windows neu starten, nicht herunterfahren.`r`n2. WinDoesNot-USB-Stick einstecken und davon starten.`r`n3. Im Installer „Parallel installieren“ wählen. Dort erscheint die Seite Windows-Daten.`r`n4. Daten übernehmen.`r`n`r`nFalls gewählt, liegen WLAN-Schlüssel im Übergabeordner im Klartext."
        } else {
            $next = "Selection saved at $root`r`n`r`n1. Restart Windows; do not shut it down.`r`n2. Insert the WinDoesNot USB stick and boot from it.`r`n3. In the installer choose Install alongside. The Windows data page appears there.`r`n4. Import your data.`r`n`r`nIf selected, WLAN keys are stored in clear text in the handoff folder."
        }
        [System.Windows.Forms.MessageBox]::Show($next, 'WinDoesNot Setup') | Out-Null
        $form.Close()
    } catch {
        $message = $_.Exception.Message
        if ($published -and $movedPrevious) {
            $message = 'Die neue Auswahl wurde gespeichert, aber der vorherige Übergabeordner konnte nicht gelöscht werden: ' + $backup + '. Er kann alte WLAN-Schlüssel enthalten.'
        }
        [System.Windows.Forms.MessageBox]::Show($message, 'WinDoesNot Setup – Fehler', 'OK', 'Error') | Out-Null
    } finally {
        if ([System.IO.Directory]::Exists($pending)) {
            try { [System.IO.Directory]::Delete($pending, $true) } catch { }
        }
    }
})
$form.Controls.Add($save)
[void]$form.ShowDialog()
