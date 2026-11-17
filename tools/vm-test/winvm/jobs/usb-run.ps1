# Runs inside the Windows test VM (SYSTEM, boot task). Tests the USB writer harness; results go to the results disk.
param([string]$Res, [string]$Pay)
$ErrorActionPreference = 'Continue'
function Log($m) { ("{0} {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) | Out-File -Append -Encoding utf8 "$Res\usb-log.txt" }
function BlockHashes($tag) {
  try {
    $fs = [IO.File]::Open("\\.\PHYSICALDRIVE0", 'Open', 'Read', 'ReadWrite')
    $out = @()
    for ($i = 0; $i -lt 16; $i++) {
      $buf = New-Object byte[] (1MB); [void]$fs.Read($buf, 0, $buf.Length)
      $out += ("{0:D2} {1}" -f $i, ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($buf)) -replace '-', '').Substring(0, 12))
    }
    $fs.Close(); $out | Out-File -Encoding ascii "$Reslocks-$tag.txt"
  } catch { }
}
function DiskHashes($tag) {
  $out = @()
  foreach ($n in 0..7) {
    try {
      $fs = [IO.File]::Open("\\.\PHYSICALDRIVE$n", 'Open', 'Read', 'ReadWrite')
      $buf = New-Object byte[] (16MB)
      $read = $fs.Read($buf, 0, $buf.Length)
      $len = (Get-WmiObject Win32_DiskDrive | Where-Object { $_.Index -eq $n }).Size
      $sha = [Security.Cryptography.SHA256]::Create().ComputeHash($buf, 0, $read)
      $out += ("disk{0} size={1} first16MiB={2}" -f $n, $len, ([BitConverter]::ToString($sha) -replace '-', ''))
      $fs.Close()
    } catch { }
  }
  $out | Out-File -Encoding ascii "$Res\hashes-$tag.txt"
}
$h = "C:\wdn-test\harness\UsbWriterHarness.exe"
New-Item -ItemType Directory -Force C:\wdn-test | Out-Null
Copy-Item -Recurse -Force "$Pay\harness" C:\wdn-test\harness
$sha = (Get-Content "$Pay\iso.sha256").Trim()
$name = (Get-Content "$Pay\iso.name").Trim()
$iso = "C:\wdn-test\iso\$name"
New-Item -ItemType Directory -Force C:\wdn-test\iso | Out-Null
Log "downloading $name from the host"
& curl.exe -s -S -o $iso "http://10.0.2.2:8130/$name" 2>> "$Res\curl-err.txt"
$got = (Get-FileHash -Algorithm SHA256 $iso).Hash
Log "download sha256=$got expected=$sha"
if ($got -ne $sha.ToUpper()) { 'DOWNLOAD HASH MISMATCH' | Out-File "$Res\FAIL.txt"; 'DONE' | Out-File "$Res\DONE.txt"; Stop-Computer -Force; exit }
Start-Sleep 20
DiskHashes 'before'
Start-Sleep 30
DiskHashes 'before2'   # baseline drift of the running system disk (no writer activity)
BlockHashes 'before2'
& $h list *> "$Res\list.txt"
$list = Get-Content "$Res\list.txt"
Log ($list -join ' | ')
$inv = $list | Where-Object { $_ -like 'INVENTORY*' }
$stick = $null
foreach ($l in $inv) { if ($l -match 'index=(\d+) .*size=(\d+)' -and [int64]$Matches[2] -gt 10GB -and [int64]$Matches[2] -lt 20GB) { $stick = [int]$Matches[1] } }
$internal = $null
foreach ($n in 1..7) {
  $d = Get-WmiObject Win32_DiskDrive | Where-Object { $_.Index -eq $n -and $_.InterfaceType -ne 'USB' }
  if ($d) { $internal = $n; break }
}
Log "stick=$stick internal=$internal"
"stick=$stick internal=$internal" | Out-File "$Res\indexes.txt"
$results = @()
function T($name, $argsList, $expectExit) {
  & $h @argsList *> "$Res\t-$name.txt"
  $code = $LASTEXITCODE
  $ok = ($code -eq $expectExit)
  $script:results += ("{0}: exit={1} expected={2} -> {3}" -f $name, $code, $expectExit, $(if ($ok) { 'PASS' } else { 'FAIL' }))
  Log $script:results[-1]
}
T 'reject-system-disk0' @('write-forced', '0', $iso, $sha) 3
BlockHashes 'after-sysreject'
Start-Sleep 40
BlockHashes 'idle-later'
if ($internal -ne $null) { T 'reject-internal' @('write-forced', "$internal", $iso, $sha) 3 }
if ($stick -ne $null) {
  T 'reject-wrong-identity' @('write-forced', "$stick", $iso, $sha, 'wrong') 3
  T 'reject-wrong-hash' @('write-forced', "$stick", $iso, ('0' * 64)) 3
  DiskHashes 'after-rejects'
  T 'write-stick' @('write', "$stick", $iso, $sha) 0
} else { $results += 'no stick found: FAIL'; Log 'no stick found' }
DiskHashes 'after'
$results | Out-File -Encoding ascii "$Res\results.txt"
'DONE' | Out-File "$Res\DONE.txt"
Stop-Computer -Force
