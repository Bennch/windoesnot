# Windows 7/8.1/10/11: tests the PowerShell stick writer (windows\WinDoesNotStick.ps1). Runs elevated; results to the results disk.
param([string]$Res, [string]$Pay)
$ErrorActionPreference = 'Continue'
function Log($m) { ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) | Out-File -Append -Encoding ascii "$Res\usb-log.txt" }
function DiskHashes($tag) {
  $out = @()
  foreach ($n in 0..7) {
    try {
      $fs = [IO.File]::Open("\\.\PHYSICALDRIVE$n", 'Open', 'Read', 'ReadWrite')
      $buf = New-Object byte[] (16MB); $read = $fs.Read($buf, 0, $buf.Length)
      $sha = [Security.Cryptography.SHA256]::Create().ComputeHash($buf, 0, $read)
      $out += ("disk{0} first16MiB={1}" -f $n, ([BitConverter]::ToString($sha) -replace '-', ''))
      $fs.Close()
    } catch { }
  }
  $out | Out-File -Encoding ascii "$Res\hashes-$tag.txt"
}
New-Item -ItemType Directory -Force C:\wdn-test | Out-Null
New-Item -ItemType Directory -Force C:\wdn-test\windows | Out-Null; Copy-Item -Recurse -Force "$Pay\windows\*" C:\wdn-test\windows
. C:\wdn-test\windows\WinDoesNotStick.ps1
$sha = (Get-Content "$Pay\iso.sha256" | Select-Object -First 1).Trim().ToUpper()
$name = (Get-Content "$Pay\iso.name" | Select-Object -First 1).Trim()
$iso = "C:\wdn-test\iso\$name"
New-Item -ItemType Directory -Force C:\wdn-test\iso | Out-Null
try { Initialize-WdnStick } catch { Log ('INIT ERROR: ' + $_.Exception.Message); if ($_.Exception.InnerException) { Log ('INNER: ' + $_.Exception.InnerException.Message) } }
$Error | ForEach-Object { Log ('ERR: ' + $_.ToString()) }
Log "PS $($PSVersionTable.PSVersion) CLR $([Environment]::Version) OS $([Environment]::OSVersion.VersionString)"
# download through the writer's own downloader (plain HTTP to the test host is allowed only for 10.0.2.2)
[WdnStick]::StartDownload("http://10.0.2.2:8130/$name", $iso, $sha)
while (-not [WdnStick]::Finished) { Start-Sleep 5 }
if ([WdnStick]::Error) { Log ('download error: ' + [WdnStick]::Error); 'DOWNLOAD FAILED' | Out-File "$Res\FAIL.txt"; 'DONE' | Out-File "$Res\DONE.txt"; Stop-Computer -Force; exit }
Log "downloaded and verified, size $((Get-Item $iso).Length)"
Start-Sleep 20
DiskHashes 'before'
Start-Sleep 30
DiskHashes 'before2'
$all = [WdnStick]::ReadDrives($iso)
$all | ForEach-Object { Log ("inventory index={0} model={1} size={2} media='{3}' letters='{4}' complete={5} removable={6} protected={7}" -f $_.Index, $_.Model, $_.SizeBytes, $_.MediaType, $_.Letters, $_.Complete, $_.Removable, $_.Protected) }
$offered = @(Get-WdnStickDrives $iso)
Log ("offered: " + ($offered | ForEach-Object { $_.ToString() }) -join ' | ')
$stick = $null; foreach ($d in $offered) { if ($d.SizeBytes -gt 10GB -and $d.SizeBytes -lt 20GB) { $stick = $d } }
$internal = $null
foreach ($n in 1..7) { $w = Get-WmiObject Win32_DiskDrive | Where-Object { $_.Index -eq $n -and $_.InterfaceType -ne 'USB' }; if ($w) { $internal = $n; break } }
$results = @()
function Expect-Refusal($label, $drive, $hash, $contains) {
  try { [WdnStick]::WriteIso($drive, $iso, $hash); $script:results += "${label}: write SUCCEEDED -> FAIL"; Log $script:results[-1] }
  catch {
    $m = $_.Exception.Message; if ($_.Exception.InnerException) { $m = $_.Exception.InnerException.Message }
    $ok = ($m -like "*$contains*")
    $script:results += ("{0}: refused '{1}' -> {2}" -f $label, $m, $(if ($ok) { 'PASS' } else { 'FAIL' })); Log $script:results[-1]
  }
}
function Fake($index, $identity, $size) { $f = New-Object WdnStickDrive; $f.Index = $index; $f.Model = 'forced'; $f.SizeBytes = $size; $f.DeviceId = "\\.\PHYSICALDRIVE$index"; $f.Identity = $identity; $f.Letters = ''; return $f }
Expect-Refusal 'reject-system-disk0' (Fake 0 'x|y|1' 8GB) $sha 'not the selected USB drive'
if ($internal -ne $null) { Expect-Refusal 'reject-internal' (Fake $internal 'x|y|1' 8GB) $sha 'not the selected USB drive' }
if ($stick -ne $null) {
  $wrong = Fake $stick.Index 'bogus|serial|1' $stick.SizeBytes
  Expect-Refusal 'reject-wrong-identity' $wrong $sha 'changed since it was selected'
  Expect-Refusal 'reject-wrong-hash' $stick ('0' * 64) 'does not match its expected checksum'
  DiskHashes 'after-rejects'
  try { [WdnStick]::WriteIso($stick, $iso, $sha); $results += 'write-stick: OK -> PASS' } catch { $results += ('write-stick: ' + $_.Exception.Message + ' -> FAIL') }
  Log $results[-1]
} else { $results += 'no stick offered -> FAIL' }
DiskHashes 'after'
$results | Out-File -Encoding ascii "$Res\results.txt"
'DONE' | Out-File "$Res\DONE.txt"
Stop-Computer -Force
