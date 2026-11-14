# Safe synthetic checks: no GUI, administrator access, real profiles or WLAN.
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourcePath = Join-Path (Split-Path -Parent $scriptDir) 'WinDoesNotSetup.ps1'
$bytes = [IO.File]::ReadAllBytes($sourcePath)
if ($bytes.Length -lt 3 -or $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191) { throw 'Script must carry a UTF-8 BOM for Windows PowerShell 2.' }
$source = [IO.File]::ReadAllText($sourcePath, [Text.Encoding]::UTF8)
$parseErrors = $null
[void][Management.Automation.PSParser]::Tokenize($source, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw ($parseErrors | Out-String) }
$functions = [regex]::Match($source, '(?s)function Json-String\(.*?(?=function Get-WindowsLabel)').Value
if (-not $functions) { throw 'Expected helper functions not found.' }
Invoke-Expression $functions
$inputText = 'A' + [char]34 + 'B' + [char]92 + 'C' + [char]1
if ((Json-String $inputText) -cne '"A\"B\\C\u0001"') { throw 'JSON escaping failed.' }
$name = 'Ada  —  test'
$item = New-HandoffItem $name 'Documents'
if ($item.Name -cne $name -or $item.Kind -cne 'Documents') { throw 'Profile selection lost its identity.' }
$cmd = [IO.File]::ReadAllText((Join-Path (Split-Path -Parent $scriptDir) 'WinDoesNotSetup.cmd'))
if ($cmd -notmatch '(?i)powershell\.exe\s+-NoProfile\s+-STA\b') { throw 'Launcher must use STA.' }
Write-Output 'PASS legacy synthetic contract checks'
