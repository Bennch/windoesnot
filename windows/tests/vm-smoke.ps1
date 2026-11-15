# vm-smoke.ps1: runs the unattended exporter against synthetic profiles. Disposable test VMs only.
# PowerShell 2.0 / .NET 3.5 compatible. Prints SMOKE-OK or SMOKE-FAIL <reason> and exits 0 or 1.
param([string]$ResultsDir = '')
$ErrorActionPreference = 'Stop'
$setup = Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) 'WinDoesNotSetup.ps1'
$users = Join-Path $env:SystemDrive 'Users'
$handoff = Join-Path $env:SystemDrive 'WinDoesNotHandoff'
$folders = @('Documents','Pictures','Music','Videos','Downloads','Desktop')
$umlautName = 'Ad' + [string][char]0x00e4 + ' M' + [string][char]0x00fc + 'ller'
$profiles = @('wdnsmoke', $umlautName, 'Test User')

function Fail([string]$why) {
    Write-Host ('SMOKE-FAIL ' + $why)
    if ($ResultsDir) { [System.IO.File]::WriteAllText((Join-Path $ResultsDir 'SMOKE-RESULT.txt'), ('SMOKE-FAIL ' + $why + "`r`n")) }
    exit 1
}
function Get-Sha256([string]$path) {
    $sha = New-Object System.Security.Cryptography.SHA256Managed
    $stream = [System.IO.File]::OpenRead($path)
    try { $hash = $sha.ComputeHash($stream) } finally { $stream.Close() }
    return ([BitConverter]::ToString($hash)).Replace('-', '').ToLower()
}

try {
    $expected = New-Object System.Text.StringBuilder
    $oneMiB = New-Object byte[] 1048576
    for ($i = 0; $i -lt $oneMiB.Length; $i++) { $oneMiB[$i] = [byte]($i % 251) }
    foreach ($name in $profiles) {
        foreach ($folder in $folders) {
            $dir = Join-Path (Join-Path $users $name) $folder
            [void][System.IO.Directory]::CreateDirectory($dir)
            [System.IO.File]::WriteAllText((Join-Path $dir 'hello.txt'), ("Hallo von $name / $folder`r`n"))
            [System.IO.File]::WriteAllText((Join-Path $dir ('Bericht ' + [char]0x00e4 + [char]0x00f6 + [char]0x00fc + [char]0x00df + '.txt')), "Umlaute im Dateinamen`r`n")
            [System.IO.File]::WriteAllBytes((Join-Path $dir 'empty.bin'), (New-Object byte[] 0))
            [System.IO.File]::WriteAllBytes((Join-Path $dir 'one-mib.bin'), $oneMiB)
            $future = Join-Path $dir 'future.txt'
            [System.IO.File]::WriteAllText($future, "Zeitstempel in der Zukunft`r`n")
            [System.IO.File]::SetLastWriteTime($future, (Get-Date).AddYears(2))
            foreach ($file in (Get-ChildItem $dir)) {
                $rel = $name + '\' + $folder + '\' + $file.Name
                [void]$expected.AppendLine((Get-Sha256 $file.FullName) + "`t" + $file.Length + "`t" + $rel)
            }
        }
    }
    if ($ResultsDir) { [System.IO.File]::WriteAllText((Join-Path $ResultsDir 'smoke-expected.txt'), $expected.ToString(), (New-Object System.Text.UTF8Encoding($false))) }

    $logFile = Join-Path $env:SystemDrive 'WinDoesNotHandoff-unattended.log'
    $errFile = Join-Path $env:TEMP 'wdn-exporter-stderr.txt'
    $outFile = Join-Path $env:TEMP 'wdn-exporter-stdout.txt'
    $process = Start-Process -FilePath 'powershell.exe' -Wait -PassThru -NoNewWindow -RedirectStandardError $errFile -RedirectStandardOutput $outFile -ArgumentList @('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',('"' + $setup + '"'),'-Unattended','-ProfileName','*','-Folders',($folders -join ','))
    if ($process.ExitCode -ne 0) {
        if ($ResultsDir) {
            foreach ($f in @($errFile, $outFile, $logFile)) { if (Test-Path -LiteralPath $f) { Copy-Item -LiteralPath $f (Join-Path $ResultsDir ('exporter-' + (Split-Path -Leaf $f))) -Force } }
        }
        Fail ('exporter exit code ' + $process.ExitCode)
    }
    $manifestPath = Join-Path $handoff 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { Fail 'manifest.json missing' }
    Add-Type -AssemblyName System.Web.Extensions
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $manifest = $serializer.DeserializeObject([System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8))
    if ($manifest['schema'] -ne 1) { Fail 'schema' }
    foreach ($name in $profiles) {
        if (-not $manifest['profiles'].ContainsKey($name)) { Fail ('profile missing in manifest: ' + $name) }
        $listed = @($manifest['profiles'][$name])
        foreach ($folder in $folders) { if ($listed -notcontains $folder) { Fail ('folder missing: ' + $name + '/' + $folder) } }
    }
    if ($ResultsDir) {
        Copy-Item -LiteralPath $manifestPath (Join-Path $ResultsDir 'manifest.json') -Force
        if (Test-Path -LiteralPath $logFile) { Copy-Item -LiteralPath $logFile (Join-Path $ResultsDir 'unattended.log') -Force }
        [System.IO.File]::WriteAllText((Join-Path $ResultsDir 'SMOKE-RESULT.txt'), "SMOKE-OK`r`n")
    }
    Write-Host 'SMOKE-OK'
    exit 0
} catch {
    Fail ('exception: ' + $_.Exception.Message)
}
