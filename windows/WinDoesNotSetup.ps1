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
# The UI types use only APIs available in .NET 3.5.
Add-Type -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;
using System.Runtime.InteropServices;
public static class SetupNative {
    [DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr handle);
    public static GraphicsPath RoundPath(int width, int height, int radius) {
        GraphicsPath p = new GraphicsPath();
        int d = Math.Min(radius * 2, Math.Min(width, height));
        if (d < 1) { p.AddRectangle(new Rectangle(0, 0, 1, 1)); return p; }
        p.AddArc(0, 0, d, d, 180, 90); p.AddArc(width-d, 0, d, d, 270, 90);
        p.AddArc(width-d, height-d, d, d, 0, 90); p.AddArc(0, height-d, d, d, 90, 90);
        p.CloseFigure(); return p;
    }
}
public class SetupCard : Panel {
    public SetupCard() { DoubleBuffered = true; ResizeRedraw = true; }
    protected override void OnResize(EventArgs e) {
        base.OnResize(e);
        using (GraphicsPath p = SetupNative.RoundPath(Width, Height, 10)) {
            Region old = Region; Region = new Region(p); if (old != null) old.Dispose();
        }
    }
    protected override void OnPaint(PaintEventArgs e) {
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using (GraphicsPath p = SetupNative.RoundPath(Width, Height, 10))
        using (Brush b = new SolidBrush(BackColor)) e.Graphics.FillPath(b, p);
        base.OnPaint(e);
    }
}
public class SetupButton : Button {
    public SetupButton() { DoubleBuffered = true; ResizeRedraw = true; FlatStyle = FlatStyle.Flat; FlatAppearance.BorderSize = 0; UseVisualStyleBackColor = false; }
    protected override void OnResize(EventArgs e) {
        base.OnResize(e);
        using (GraphicsPath p = SetupNative.RoundPath(Width, Height, 8)) {
            Region old = Region; Region = new Region(p); if (old != null) old.Dispose();
        }
    }
}
'@ -ReferencedAssemblies System.Windows.Forms,System.Drawing

function Enable-DoubleBuffer($control) {
    $property = [System.Windows.Forms.Control].GetProperty('DoubleBuffered', [System.Reflection.BindingFlags] 'Instance,NonPublic')
    $property.SetValue($control, $true, $null)
}
function New-Label([string]$text, [int]$x, [int]$y, [int]$width, [int]$height, [single]$size, [bool]$bold, $color) {
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $text
    $label.SetBounds($x, $y, $width, $height)
    $style = [System.Drawing.FontStyle]::Regular
    if ($bold) { $style = [System.Drawing.FontStyle]::Bold }
    $label.Font = New-Object System.Drawing.Font($script:fontFamily, $size, $style)
    $label.ForeColor = $color
    $label.BackColor = [System.Drawing.Color]::Transparent
    return $label
}
function New-Card([int]$x, [int]$y, [int]$width, [int]$height) {
    $card = New-Object SetupCard
    $card.SetBounds($x, $y, $width, $height)
    $card.BackColor = [System.Drawing.Color]::FromArgb(38,38,42)
    return $card
}
function New-SetupButton([string]$text, [bool]$primary) {
    $button = New-Object SetupButton
    $button.Text = $text
    if ($primary) {
        $button.BackColor = [System.Drawing.Color]::FromArgb(254,111,45)
        $button.ForeColor = [System.Drawing.Color]::FromArgb(20,20,20)
        $button.FlatAppearance.MouseOverBackColor = [System.Drawing.Color]::FromArgb(255,145,88)
        $button.FlatAppearance.MouseDownBackColor = [System.Drawing.Color]::FromArgb(220,85,25)
    } else {
        $button.BackColor = [System.Drawing.Color]::FromArgb(48,48,52)
        $button.ForeColor = [System.Drawing.Color]::FromArgb(238,238,238)
        $button.FlatAppearance.MouseOverBackColor = [System.Drawing.Color]::FromArgb(65,65,69)
    }
    return $button
}
function Read-EmbeddedImage([string]$encoded) {
    $bytes = [Convert]::FromBase64String($encoded)
    $stream = New-Object System.IO.MemoryStream(,$bytes)
    try {
        $sourceBitmap = New-Object System.Drawing.Bitmap($stream)
        try { return New-Object System.Drawing.Bitmap($sourceBitmap) } finally { $sourceBitmap.Dispose() }
    } finally { $stream.Dispose() }
}
$iconPng = 'iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAADhklEQVR42tWaT2sTWxjGf++ZSeOiabwSkHhBctUWWnFxof0IRXQjgh/g4l27u6XgRtxZ3AiCC0G/wC2Im4r0gmu10F2LrVZbsNkErumUknT+HBfnjBmqi2YmxplnMZkkzPA8533P+4f3CBaNxnlASKAGXAauAdNAHTjBcNABmsAK8Bx4CbTiP7XWbG9/gJhxo3Eh+fAIcB24ZYmX+bXoWiEPgWfAoREB29vvkSPka8Bd4OYQV7sfIU+AO7E1tAbn5MlTSfKPgL8Al/zBBWaAP4BXwIFIT8AIcM+SzzsuAqPAf0Co7I/Xgb8pDm5azijrOrdysFn7wQnLuaZsqJymeJgGLisb58sFFFAGrqmCrv43KyibYYuKusphwuprMysKjoFnXK0hsgVXrzjUiAgKEMmpgJh4tQTjFcXEmFArG7atrmZzT7PhRbR9BipkIAIiDZUSXD3jcOOsy2RVqLiSNABeoFlvaxZ3ApZ2Qzwf1ABESKNxQWd5Qajh3KgwP1Vitu7gKkOY3kevyxAIIlhuhiys+Wztaxz5hRaILPn7f44wU1OgjSt9516JG1fgyu8OtbIwt3rIx32dyRIqi89XSjA/VeqRP85z9jJTU8xPlaiUfiz6pwuIMD4/W3eOTf6oiNm6w9UzDhFDFqC1iTY3zrq4qj/ySRGuMu+oZrCCSrv64xXFZFXSsU+omKwK4xWV2gopLaCZGLOhMiMqrjAxJjbxDW0P2CSV3QAg2IQnw93EeYFKu3atrgk9WZxIrBlaXU1aW6YSICJs7Gm8QGdeQS/QbOyZYm9oAhSw6UWst7ObYL2t2fSi1L6c0gLQ9mFxJyCI0mkQTF20uBPQ9tNXpyrL5lnaDVluhiD9iRB7WW6GLO2GmSJJ6mdFwPNhYc3nbSs6toiY/NtWxMKaj+dn6w0yhVElsLWv+Wf1kBefQwJtyByN6vF3EQg0vPgcMrd6yFbGSnQg/cD3DY3DZFUVp6E5bku5sWeizaBbyoEJKHxTn9zcDkeZCuSrlMhXLdQpMP+OwkwDi4qmwkwAi4oVhZnDdgtIvgs8V5ghchGtsAK8VHbm+rBgm7ljObfiMPoMeFogAU8t529z4hB4gxkiX8w5+X+BOcCzAn6LM+UBZgI+ClzK4bS+Azy25HtHDb58+Z/EcYMDzAT8HWZ2djoHQrrAa+A28CBeebCHPSjgcRuAT5/eA/AVeglJeiZ79vgAAAAASUVORK5CYII='
$logoPng = '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'
$iconBitmap = Read-EmbeddedImage $iconPng
$iconHandle = $iconBitmap.GetHicon()
try {
    $temporaryIcon = [System.Drawing.Icon]::FromHandle($iconHandle)
    $script:appIcon = [System.Drawing.Icon]$temporaryIcon.Clone()
    $temporaryIcon.Dispose()
} finally { [void][SetupNative]::DestroyIcon($iconHandle); $iconBitmap.Dispose() }
$script:logoBitmap = Read-EmbeddedImage $logoPng
# The embedded artwork uses dark lettering; brighten it for the dark sidebar.
for ($y = 0; $y -lt $script:logoBitmap.Height; $y++) {
    for ($x = 0; $x -lt $script:logoBitmap.Width; $x++) {
        $pixel = $script:logoBitmap.GetPixel($x, $y)
        if ($pixel.A -gt 0 -and $pixel.R -lt 80 -and $pixel.G -lt 80 -and $pixel.B -lt 80) {
            $script:logoBitmap.SetPixel($x, $y, [System.Drawing.Color]::FromArgb($pixel.A, 238, 238, 238))
        }
    }
}
$script:form = New-Object System.Windows.Forms.Form
$script:form.Text = 'WinDoesNot Setup'
$script:form.Icon = $script:appIcon
$script:form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
$script:form.AutoScaleDimensions = New-Object -TypeName System.Drawing.SizeF -ArgumentList 96,96
$script:form.ClientSize = New-Object -TypeName System.Drawing.Size -ArgumentList 760,540
$script:form.MinimumSize = New-Object -TypeName System.Drawing.Size -ArgumentList 650,440
$script:form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$script:form.BackColor = [System.Drawing.Color]::FromArgb(27,27,31)
$script:form.ForeColor = [System.Drawing.Color]::FromArgb(238,238,238)
Enable-DoubleBuffer $script:form
$fontName = 'Tahoma'
$installedFonts = New-Object System.Drawing.Text.InstalledFontCollection
foreach ($family in $installedFonts.Families) { if ($family.Name -eq 'Segoe UI') { $fontName = 'Segoe UI'; break } }
$script:fontFamily = New-Object System.Drawing.FontFamily($fontName)
$installedFonts.Dispose()
$script:form.Font = New-Object System.Drawing.Font($script:fontFamily, 9.5, [System.Drawing.FontStyle]::Regular)
$white = [System.Drawing.Color]::FromArgb(238,238,238)
$muted = [System.Drawing.Color]::FromArgb(170,170,170)
$orange = [System.Drawing.Color]::FromArgb(254,111,45)
$sidebar = New-Object System.Windows.Forms.Panel
$sidebar.SetBounds(0,0,205,540)
$sidebar.Anchor = 'Top,Bottom,Left'
$sidebar.BackColor = [System.Drawing.Color]::FromArgb(20,20,20)
Enable-DoubleBuffer $sidebar
$script:form.Controls.Add($sidebar)
$logo = New-Object System.Windows.Forms.PictureBox
$logo.Image = $script:logoBitmap
$logo.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
$logo.SetBounds(18,20,135,30)
$sidebar.Controls.Add($logo)
$setupWord = New-Label 'Setup' 155 23 48 24 10 $true $muted
$sidebar.Controls.Add($setupWord)
if ($isGerman) { $stepNames = @('Willkommen','Auswahl','Fertig') } else { $stepNames = @('Welcome','Selection','Done') }
$script:stepLabels = @()
$script:stepBars = @()
for ($i = 0; $i -lt 3; $i++) {
    $bar = New-Object System.Windows.Forms.Panel
    $bar.SetBounds(0,(95 + 50 * $i),4,36)
    $bar.BackColor = $orange
    $sidebar.Controls.Add($bar)
    $script:stepBars += $bar
    $stepLabel = New-Label '' 20 (99 + 50 * $i) 180 30 10 $false $muted
    $sidebar.Controls.Add($stepLabel)
    $script:stepLabels += $stepLabel
}
$script:pages = @()
for ($i = 0; $i -lt 3; $i++) {
    $page = New-Object System.Windows.Forms.Panel
    $page.SetBounds(225,20,515,445)
    $page.Anchor = 'Top,Bottom,Left,Right'
    Enable-DoubleBuffer $page
    $script:form.Controls.Add($page)
    $script:pages += $page
}
$shownLabel = $windowsLabel -replace '^(Windows [0-9.]+).*$','$1'
if ($isGerman) {
    $welcomeTitle = 'Willkommen bei'; $welcomeText = "Bereite deinen Umzug von $shownLabel vor. Deine Dateien bleiben unverändert, Windows läuft weiter. Nur deine Auswahl wird gespeichert."
    $cardTitles = @('Dateien','WLAN','Browser'); $cardTexts = @('Ordner auswählen','Netzwerke mitnehmen','Firefox auswählen')
    $selectTitle = 'Deine Auswahl'; $selectText = 'Wähle Konten und Ordner für den Umzug.'
    $wifiText = 'Gespeicherte WLAN-Schlüssel exportieren (im Klartext gespeichert)'
    $noticeText = 'Umgeleitete oder nicht lokale Ordner fehlen möglicherweise. Chrome/Edge-Passwörter als CSV exportieren. Firefox schließen; Passwortübernahme ungeprüft.'
    $doneTitle = 'Auswahl gespeichert'; $doneText = "Gespeichert unter $root`r`n`r`n1. Windows neu starten, nicht herunterfahren.`r`n2. WinDoesNot-Medium einstecken und davon starten.`r`n3. Im Installer 'Parallel installieren' wählen und auf der Seite Windows-Daten den Umzug starten.`r`n`r`nGewählte WLAN-Schlüssel liegen im Übergabeordner im Klartext."
} else {
    $welcomeTitle = 'Welcome to'; $welcomeText = "Prepare your move from $shownLabel. Your files remain unchanged and Windows keeps running. Only your selection is saved."
    $cardTitles = @('Files','Wi-Fi','Browser'); $cardTexts = @('Choose folders','Bring networks','Select Firefox')
    $selectTitle = 'Your selection'; $selectText = 'Choose accounts and folders to migrate.'
    $wifiText = 'Export saved Wi-Fi keys (stored in clear text)'
    $noticeText = 'Redirected or non-local folders may be missing. Export Chrome/Edge passwords as CSV. Close Firefox; password import is unverified.'
    $doneTitle = 'Selection saved'; $doneText = "Saved at $root`r`n`r`n1. Restart Windows; do not shut it down.`r`n2. Insert and boot from the WinDoesNot medium.`r`n3. Choose 'Install alongside' in the installer and start the migration on the Windows data page.`r`n`r`nSelected Wi-Fi keys are stored in clear text in the handoff folder."
}
$script:pages[0].Controls.Add((New-Label $welcomeTitle 0 20 500 34 20 $true $white))
$script:pages[0].Controls.Add((New-Label 'WinDoesNot.' 0 55 500 42 24 $true $orange))
$script:pages[0].Controls.Add((New-Label $welcomeText 0 110 500 78 10 $false $muted))
for ($i = 0; $i -lt 3; $i++) {
    $card = New-Card (165 * $i) 210 155 100
    $card.Controls.Add((New-Label $cardTitles[$i] 12 14 130 28 11 $true $white))
    $card.Controls.Add((New-Label $cardTexts[$i] 12 48 130 42 9 $false $muted))
    $script:pages[0].Controls.Add($card)
}
$script:pages[1].Controls.Add((New-Label $selectTitle 0 4 500 38 20 $true $white))
$script:pages[1].Controls.Add((New-Label $selectText 0 48 500 30 10 $false $muted))
$script:list = New-Object System.Windows.Forms.CheckedListBox
$script:list.SetBounds(0,80,510,210)
$script:list.Anchor = 'Top,Bottom,Left,Right'
$script:list.IntegralHeight = $false
$script:list.CheckOnClick = $true
$script:list.DisplayMember = 'Label'
$script:list.BackColor = [System.Drawing.Color]::FromArgb(20,20,20)
$script:list.ForeColor = $white
$script:list.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
foreach ($item in @(Get-HandoffItems $usersRoot $defaultFolders)) {
    $idx = $script:list.Items.Add($item)
    if ($item.Name -eq $env:USERNAME) { $script:list.SetItemChecked($idx, $true) }
}
$script:pages[1].Controls.Add($script:list)
$script:wifi = New-Object System.Windows.Forms.CheckBox
$script:wifi.Text = $wifiText
$script:wifi.SetBounds(0,300,510,36)
$script:wifi.Anchor = 'Bottom,Left,Right'
$script:wifi.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$script:wifi.ForeColor = $white
$script:pages[1].Controls.Add($script:wifi)
$notice = New-Label $noticeText 0 340 510 95 9 $false $muted
$notice.Anchor = 'Bottom,Left,Right'
$script:pages[1].Controls.Add($notice)
$script:pages[2].Controls.Add((New-Label $doneTitle 0 20 500 45 20 $true $orange))
$doneCard = New-Card 0 80 510 300
$doneCard.Anchor = 'Top,Left,Right'
$doneLabel = New-Label $doneText 18 16 470 270 10 $false $white
$doneLabel.Anchor = 'Top,Left,Right'
$doneCard.Controls.Add($doneLabel)
$script:pages[2].Controls.Add($doneCard)
# Optional: create the installer USB stick (download or choose the ISO, write, verify) - needs WinDoesNotStick.ps1 next to this script.
$stickScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'WinDoesNotStick.ps1'
if (Test-Path $stickScript) {
    . $stickScript
    if ($isGerman) { $stickText = 'USB-Stick erstellen...' } else { $stickText = 'Create USB stick...' }
    $stickButton = New-SetupButton $stickText $false
    $stickButton.SetBounds(0,392,230,36)
    $stickButton.Anchor = 'Top,Left'
    $stickButton.Add_Click({ try { Show-WdnStickDialog $script:isGerman $script:form } catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'WinDoesNot Setup', 'OK', 'Error') | Out-Null } })
    $script:pages[2].Controls.Add($stickButton)
}
$script:back = New-SetupButton '' $false
$script:back.SetBounds(225,485,120,36)
$script:back.Anchor = 'Bottom,Left'
$script:form.Controls.Add($script:back)
$script:next = New-SetupButton '' $true
$script:next.SetBounds(560,485,180,36)
$script:next.Anchor = 'Bottom,Right'
$script:form.Controls.Add($script:next)
$script:step = 0
$script:isGerman = $isGerman
$script:stepNames = $stepNames
$script:root = $root
$script:windowsLabel = $windowsLabel
function Show-SetupStep {
    for ($j = 0; $j -lt 3; $j++) {
        $script:pages[$j].Visible = ($j -eq $script:step)
        $script:stepBars[$j].Visible = ($j -eq $script:step)
        $prefix = ([string]($j + 1)) + '   '
        if ($j -lt $script:step) { $prefix = [string][char]0x2713 + '   ' }
        $script:stepLabels[$j].Text = $prefix + $script:stepNames[$j]
        if ($j -eq $script:step) { $script:stepLabels[$j].ForeColor = [System.Drawing.Color]::FromArgb(238,238,238) }
        else { $script:stepLabels[$j].ForeColor = [System.Drawing.Color]::FromArgb(170,170,170) }
    }
    $script:back.Visible = ($script:step -gt 0)
    if ($script:isGerman) {
        $script:back.Text = 'Zurück'
        if ($script:step -eq 0) { $script:next.Text = 'Weiter' } elseif ($script:step -eq 1) { $script:next.Text = 'Auswahl speichern' } else { $script:next.Text = 'Fertig' }
    } else {
        $script:back.Text = 'Back'
        if ($script:step -eq 0) { $script:next.Text = 'Next' } elseif ($script:step -eq 1) { $script:next.Text = 'Save selection' } else { $script:next.Text = 'Done' }
    }
}
$script:back.Add_Click({ $script:step--; Show-SetupStep })
$script:next.Add_Click({
    if ($script:step -eq 2) { $script:form.Close(); return }
    if ($script:step -eq 1) {
        try { Save-Handoff (Group-Selection $script:list.CheckedItems) $script:wifi.Checked $script:root $script:windowsLabel }
        catch {
            if ($script:isGerman) { $errorTitle = 'WinDoesNot Setup - Fehler' } else { $errorTitle = 'WinDoesNot Setup - Error' }
            [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, $errorTitle, 'OK', 'Error') | Out-Null
            return
        }
    }
    $script:step++; Show-SetupStep
})
$script:form.Add_Load({
    $graphics = $script:form.CreateGraphics()
    try { $dpiFactor = $graphics.DpiX / 96.0 } finally { $graphics.Dispose() }
    $workArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $width = [Math]::Min($script:form.Width, $workArea.Width)
    $height = [Math]::Min($script:form.Height, $workArea.Height)
    $script:form.Size = New-Object -TypeName System.Drawing.Size -ArgumentList $width,$height
    $left = $workArea.Left + [int](($workArea.Width - $width) / 2)
    $top = $workArea.Top + [int](($workArea.Height - $height) / 2)
    $script:form.Location = New-Object -TypeName System.Drawing.Point -ArgumentList $left,$top
})
Show-SetupStep
try { [void]$script:form.ShowDialog() } finally {
    $script:form.Dispose(); $script:logoBitmap.Dispose(); $script:appIcon.Dispose(); $script:fontFamily.Dispose()
}
