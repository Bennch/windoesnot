#!/usr/bin/env python3
"""Heuristic static regression guard, not a PowerShell 2 parser or runtime test."""
from pathlib import Path
import re
root = Path(__file__).resolve().parent.parent
script = (root / 'windows/WinDoesNotSetup.ps1').read_text(encoding='utf-8-sig')
patterns = [r'\b(?:ConvertTo-Json|ConvertFrom-Json|Get-CimInstance|Get-FileHash|Invoke-WebRequest|Invoke-RestMethod)\b', r'\[ordered\]', r'(?i)\s-Raw\b|\s-NoNewline\b', r'\.[ \t]*(?:Where|ForEach)[ \t]*\(', r'\b(?:IsNullOrWhiteSpace|HasFlag|EnumerateFiles|CopyTo)\s*\(', r'\[(?:Tuple|Lazy)(?:\[|\])', r'\?\.', r'(?i)-NoNewWindow[^\n]*-WindowStyle|-WindowStyle[^\n]*-NoNewWindow']
for pattern in patterns:
    assert not re.search(pattern, script, re.I), pattern
assert script.startswith('# WinDoesNot')
assert '-NoProfile -STA' in (root / 'windows/WinDoesNotSetup.cmd').read_text()
assert 'CurrentUICulture.TwoLetterISOLanguageName' in script
for phrase in ('Windows neu starten', 'Parallel installieren', 'Restart Windows', 'Install alongside'):
    assert phrase in script, phrase
print('PASS legacy static patterns (not a runtime test)')

# PowerShell treats typographic quotes as string delimiters. A German „...“ inside a string breaks the whole script
# (found in a Windows 10 VM on 2026-11-15), so they must never appear in the exporter or the smoke script.
import pathlib as _pl
for _name in ('windows/WinDoesNotSetup.ps1', 'windows/tests/vm-smoke.ps1'):
    _text = (_pl.Path(__file__).resolve().parents[1] / _name).read_bytes().decode('utf-8-sig')
    for _number, _line in enumerate(_text.split('\n'), 1):
        assert not any(_c in _line for _c in '\u201c\u201d\u201e\u201f\u2018\u2019\u201a\u201b'), _name + ':' + str(_number) + ' typographic quote'
print('PASS powershell scripts contain no typographic quotes')

# A script variable must not share its name with a parameter (PowerShell names are case-insensitive): a $folders
# variable silently overwrote the -Folders parameter in unattended mode.
import re as _re
_script = (_pl.Path(__file__).resolve().parents[1] / 'windows/WinDoesNotSetup.ps1').read_bytes().decode('utf-8-sig')
_params = [m.lower() for m in _re.findall(r'\[(?:switch|string|bool|int)\]\s*\$(\w+)', _script.split(')\n', 1)[0])]
for _name in _params:
    assert not _re.search(r'^\s*\$(?:script:)?' + _name + r'\s*=', _script, _re.M | _re.I), 'parameter shadowed by variable: ' + _name
print('PASS no parameter is shadowed by a script variable')
