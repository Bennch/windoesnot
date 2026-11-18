# WinDoesNot: create the installer USB stick from Windows PowerShell (Windows 7 to 11).
# Dot-sourced by WinDoesNotSetup.ps1 (which provides New-Label, New-SetupButton and the dark theme) and also usable
# headless for tests:  . .\WinDoesNotStick.ps1 ; Get-WdnStickDrives ; Write-WdnStick ...
# The C# part (WinDoesNotStick.cs) is compiled by Add-Type and works with .NET 3.5 / PowerShell 2.

$script:StickDir = Split-Path -Parent $MyInvocation.MyCommand.Path
function Initialize-WdnStick {
    if ($script:StickLoaded) { return }
    $source = [System.IO.File]::ReadAllText((Join-Path $script:StickDir 'WinDoesNotStick.cs'))
    Add-Type -TypeDefinition $source -ReferencedAssemblies System.Management
    $script:StickLoaded = $true
}

function Get-WdnStickDrives([string]$IsoPath) { Initialize-WdnStick; return @([WdnStick]::OfferedDrives($IsoPath)) }

# Reads the current release feed and returns @{ Url=..; Sha256=..; Bytes=.. } for the language (de|en).
function Get-WdnReleaseIso([string]$Language, [string]$FeedUrl) {
    Initialize-WdnStick
    if (-not $FeedUrl) { $FeedUrl = 'https://windoesnot.me/releases.json' }
    $json = [WdnStick]::FetchText($FeedUrl)
    $iso = $json.IndexOf('"iso"')
    if ($iso -lt 0) { throw 'The release feed has no ISO entry.' }
    $lang = $json.IndexOf('"' + $Language + '"', $iso)
    if ($lang -lt 0) { throw 'The release feed has no ISO for this language.' }
    $tail = $json.Substring($lang)
    $url = [regex]::Match($tail, '"url"\s*:\s*"([^"]+)"').Groups[1].Value
    $sha = [regex]::Match($tail, '"sha256"\s*:\s*"([0-9a-fA-F]{64})"').Groups[1].Value
    $bytes = [regex]::Match($tail, '"bytes"\s*:\s*([0-9]+)').Groups[1].Value
    if (-not $url -or -not $sha) { throw 'The release feed entry is incomplete.' }
    if (-not $url.StartsWith('https://download.windoesnot.me/')) { throw 'The release feed points to an unexpected host.' }
    return @{ Url = $url; Sha256 = $sha.ToUpper(); Bytes = $bytes }
}

# Headless write used by tests: returns 0 on success, throws on refusal.
function Write-WdnStick($Drive, [string]$IsoPath, [string]$Sha256) {
    Initialize-WdnStick
    [WdnStick]::WriteIso($Drive, $IsoPath, $Sha256)
}

function Show-WdnStickDialog([bool]$IsGerman, $Owner) {
    Initialize-WdnStick
    $white = [System.Drawing.Color]::FromArgb(238,238,238)
    $muted = [System.Drawing.Color]::FromArgb(170,170,170)
    $orange = [System.Drawing.Color]::FromArgb(254,111,45)
    $dark = [System.Drawing.Color]::FromArgb(20,20,20)
    if ($IsGerman) {
        $t = @{
            Title='USB-Stick erstellen'; Intro='Lädt die aktuelle WinDoesNot-ISO, prüft sie und schreibt sie auf einen USB-Stick. Danach startest du den PC von diesem Stick und wählst im Installer "Parallel dazu installieren". Windows bleibt unverändert.'
            Download='Aktuelle ISO herunterladen (ca. 5 GB)'; Own='Vorhandene ISO-Datei verwenden'; Browse='Datei wählen...'; ShaLabel='SHA-256 der ISO (von windoesnot.me/download):'
            Drive='USB-Stick:'; Refresh='Aktualisieren'; Warn='ACHTUNG: Alles auf dem gewählten Stick wird gelöscht. Es werden nur USB-Wechselmedien mit 512-Byte-Sektoren angeboten, nie die Windows-Platte.'
            Confirm='Zur Bestätigung tippe LÖSCHEN:'; Start='Stick erstellen'; Cancel='Abbrechen'; Close='Schließen'; NoDrive='Kein geeigneter USB-Stick gefunden. Stick einstecken und "Aktualisieren" wählen.'
            Checking='ISO wird geprüft...'; Downloading='ISO wird geladen...'; Writing='Stick wird geschrieben...'; Verifying='Stick wird geprüft...'
            DoneTitle='Fertig'; DoneText='Der Stick ist geschrieben und geprüft. Starte den PC neu und starte vom USB-Stick (meist öffnet F12, F11, F8 oder Esc das Startmenü). Wähle im WinDoesNot-Installer "Parallel dazu installieren". Der Explorer bietet evtl. an, Laufwerke zu formatieren: bitte "Abbrechen" wählen.'
            NoIso='Bitte eine ISO-Datei wählen und ihre SHA-256-Prüfsumme eintragen.'; NoNet='Der Download ist nicht möglich (keine Verbindung oder dieses Windows unterstützt kein TLS 1.2). Lade die ISO auf windoesnot.me/download in einem Browser und wähle sie hier als Datei.'
            Err='Fehler'; Cancelled='Abgebrochen.'
        }
        $lang = 'de'
    } else {
        $t = @{
            Title='Create USB stick'; Intro='Downloads the current WinDoesNot ISO, verifies it and writes it to a USB stick. Then start the PC from that stick and choose "Install alongside" in the installer. Windows stays unchanged.'
            Download='Download the current ISO (about 5 GB)'; Own='Use an existing ISO file'; Browse='Choose file...'; ShaLabel='SHA-256 of the ISO (from windoesnot.me/download):'
            Drive='USB stick:'; Refresh='Refresh'; Warn='WARNING: Everything on the chosen stick is erased. Only removable USB drives with 512-byte sectors are offered, never the Windows disk.'
            Confirm='To confirm, type ERASE:'; Start='Create stick'; Cancel='Cancel'; Close='Close'; NoDrive='No suitable USB stick found. Insert a stick and choose "Refresh".'
            Checking='Checking the ISO...'; Downloading='Downloading the ISO...'; Writing='Writing the stick...'; Verifying='Verifying the stick...'
            DoneTitle='Done'; DoneText='The stick is written and verified. Restart the PC and start from the USB stick (usually F12, F11, F8 or Esc opens the boot menu). In the WinDoesNot installer choose "Install alongside". Explorer may offer to format drives: please choose "Cancel".'
            NoIso='Please choose an ISO file and enter its SHA-256 checksum.'; NoNet='The download is not possible (no connection, or this Windows has no TLS 1.2). Download the ISO at windoesnot.me/download in a browser and choose it here as a file.'
            Err='Error'; Cancelled='Cancelled.'
        }
        $lang = 'en'
    }
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'WinDoesNot - ' + $t.Title
    $form.ClientSize = New-Object System.Drawing.Size(640, 520)
    $form.StartPosition = 'CenterParent'; $form.FormBorderStyle = 'FixedDialog'; $form.MaximizeBox = $false; $form.MinimizeBox = $false
    $form.BackColor = [System.Drawing.Color]::FromArgb(27,27,31); $form.ForeColor = $white
    if ($Owner) { $form.Font = $Owner.Font }
    function L($text, $x, $y, $w, $h, $color) { $l = New-Object System.Windows.Forms.Label; $l.Text = $text; $l.SetBounds($x,$y,$w,$h); $l.ForeColor = $color; $l.BackColor = [System.Drawing.Color]::Transparent; return $l }
    $form.Controls.Add((L $t.Title 20 14 600 30 $white)); $form.Controls[0].Font = New-Object System.Drawing.Font($form.Font.FontFamily, 16, [System.Drawing.FontStyle]::Bold)
    $form.Controls.Add((L $t.Intro 20 50 600 52 $muted))
    $rbDownload = New-Object System.Windows.Forms.RadioButton; $rbDownload.Text = $t.Download; $rbDownload.SetBounds(20,108,600,24); $rbDownload.Checked = $true; $rbDownload.ForeColor = $white
    $rbOwn = New-Object System.Windows.Forms.RadioButton; $rbOwn.Text = $t.Own; $rbOwn.SetBounds(20,134,400,24); $rbOwn.ForeColor = $white
    $browse = New-Object System.Windows.Forms.Button; $browse.Text = $t.Browse; $browse.SetBounds(430,132,190,26); $browse.Enabled = $false
    $isoBox = New-Object System.Windows.Forms.TextBox; $isoBox.SetBounds(40,162,580,24); $isoBox.Enabled = $false; $isoBox.ReadOnly = $true
    $shaLabel = L $t.ShaLabel 40 190 580 20 $muted
    $shaBox = New-Object System.Windows.Forms.TextBox; $shaBox.SetBounds(40,212,580,24); $shaBox.Enabled = $false
    foreach ($c in @($rbDownload,$rbOwn,$browse,$isoBox,$shaLabel,$shaBox)) { $form.Controls.Add($c) }
    $form.Controls.Add((L $t.Drive 20 252 100 22 $white))
    $combo = New-Object System.Windows.Forms.ComboBox; $combo.SetBounds(20,276,480,24); $combo.DropDownStyle = 'DropDownList'
    $refresh = New-Object System.Windows.Forms.Button; $refresh.Text = $t.Refresh; $refresh.SetBounds(510,274,110,28)
    $form.Controls.Add($combo); $form.Controls.Add($refresh)
    $warn = L $t.Warn 20 312 600 40 $orange; $form.Controls.Add($warn)
    $form.Controls.Add((L $t.Confirm 20 360 220 22 $white))
    $confirm = New-Object System.Windows.Forms.TextBox; $confirm.SetBounds(240,357,160,24); $form.Controls.Add($confirm)
    $status = L '' 20 394 600 40 $muted; $form.Controls.Add($status)
    $bar = New-Object System.Windows.Forms.ProgressBar; $bar.SetBounds(20,436,600,18); $bar.Minimum = 0; $bar.Maximum = 1000; $form.Controls.Add($bar)
    $start = New-Object System.Windows.Forms.Button; $start.Text = $t.Start; $start.SetBounds(400,472,220,32); $start.Enabled = $false
    $cancel = New-Object System.Windows.Forms.Button; $cancel.Text = $t.Close; $cancel.SetBounds(20,472,160,32)
    $form.Controls.Add($start); $form.Controls.Add($cancel)
    $state = @{ Busy = $false; Mode = ''; Iso = ''; Sha = ''; Drive = $null; Release = $null }
    $timer = New-Object System.Windows.Forms.Timer; $timer.Interval = 400

    $reload = {
        $combo.Items.Clear()
        $iso = ''; if ($rbOwn.Checked) { $iso = $isoBox.Text }
        try { foreach ($d in (Get-WdnStickDrives $iso)) { [void]$combo.Items.Add($d) } } catch { $status.Text = $t.Err + ': ' + $_.Exception.Message }
        if ($combo.Items.Count -eq 1) { $combo.SelectedIndex = 0 }
        if ($combo.Items.Count -eq 0 -and -not $state.Busy) { $status.Text = $t.NoDrive }
    }
    $update = {
        $typed = $confirm.Text.Trim().ToUpper()
        $ok = ($typed -eq 'LÖSCHEN' -or $typed -eq 'LOESCHEN' -or $typed -eq 'ERASE')
        $start.Enabled = ((-not $state.Busy) -and ($combo.SelectedItem -ne $null) -and $ok)
    }
    $rbOwn.Add_CheckedChanged({ $on = $rbOwn.Checked; $browse.Enabled = $on; $isoBox.Enabled = $on; $shaBox.Enabled = $on; & $reload })
    $browse.Add_Click({
        $dlg = New-Object System.Windows.Forms.OpenFileDialog; $dlg.Filter = 'ISO (*.iso)|*.iso'
        if ($dlg.ShowDialog() -eq 'OK') { $isoBox.Text = $dlg.FileName; & $reload }
    })
    $refresh.Add_Click({ & $reload })
    $combo.Add_SelectedIndexChanged({ $confirm.Text = ''; & $update })
    $confirm.Add_TextChanged({ & $update })
    $finish = {
        $timer.Stop(); $state.Busy = $false; $cancel.Text = $t.Close; $bar.Value = 0
        if ([WdnStick]::Error) { $status.ForeColor = $orange; $status.Text = $t.Err + ': ' + [WdnStick]::Error; $confirm.Text = '' }
        & $update; $combo.Enabled = $true; $refresh.Enabled = $true
    }
    $timer.Add_Tick({
        $total = [WdnStick]::Total; $done = [WdnStick]::Done
        if ($total -gt 0) { $bar.Value = [int][Math]::Min(1000, ($done * 1000 / $total)) }
        $phase = [WdnStick]::Phase
        if ($phase -eq 'download') { $status.Text = $t.Downloading + ' ' + [int]($done / 1MB) + ' / ' + [int]($total / 1MB) + ' MB' }
        elseif ($phase -eq 'hash' -or $phase -eq 'check') { $status.Text = $t.Checking }
        elseif ($phase -eq 'write') { $status.Text = $t.Writing + ' ' + [int]($done / 1MB) + ' / ' + [int]($total / 1MB) + ' MB' }
        elseif ($phase -eq 'verify') { $status.Text = $t.Verifying + ' ' + [int]($done / 1MB) + ' / ' + [int]($total / 1MB) + ' MB' }
        if (-not [WdnStick]::Finished) { return }
        if ([WdnStick]::Error) { & $finish; return }
        if ($state.Mode -eq 'download') {
            # download done and verified: now write
            $state.Mode = 'write'; [WdnStick]::StartWrite($state.Drive, $state.Iso, $state.Sha); return
        }
        & $finish
        $bar.Value = 1000; $status.ForeColor = $white; $status.Text = $t.DoneTitle + ': ' + $t.DoneText
        $start.Enabled = $false
    })
    $start.Add_Click({
        $status.ForeColor = $muted
        $state.Drive = $combo.SelectedItem
        try {
            if ($rbOwn.Checked) {
                if (-not $isoBox.Text -or $shaBox.Text.Trim().Length -ne 64) { $status.Text = $t.NoIso; return }
                $state.Iso = $isoBox.Text; $state.Sha = $shaBox.Text.Trim().ToUpper(); $state.Mode = 'write'
            } else {
                $status.Text = $t.Checking; $form.Cursor = 'WaitCursor'; [System.Windows.Forms.Application]::DoEvents()
                try { $rel = Get-WdnReleaseIso $lang } catch { $form.Cursor = 'Default'; $status.ForeColor = $orange; $status.Text = $t.NoNet; return }
                $form.Cursor = 'Default'
                $state.Iso = Join-Path $env:TEMP ([System.IO.Path]::GetFileName($rel.Url)); $state.Sha = $rel.Sha256; $state.Mode = 'download'
            }
            $state.Busy = $true; $start.Enabled = $false; $combo.Enabled = $false; $refresh.Enabled = $false; $cancel.Text = $t.Cancel
            if ($state.Mode -eq 'download') { [WdnStick]::StartDownload($rel.Url, $state.Iso, $state.Sha) } else { [WdnStick]::StartWrite($state.Drive, $state.Iso, $state.Sha) }
            $timer.Start()
        } catch { $status.ForeColor = $orange; $status.Text = $t.Err + ': ' + $_.Exception.Message; $state.Busy = $false; & $update }
    })
    $cancel.Add_Click({
        if ($state.Busy) { [WdnStick]::Cancel = $true; $status.Text = $t.Cancelled } else { $form.Close() }
    })
    $form.Add_FormClosing({ if ($state.Busy) { $_.Cancel = $true } })
    $form.Add_Shown({ & $reload })
    try { [void]$form.ShowDialog($Owner) } finally { $timer.Dispose(); $form.Dispose() }
}
