#!/usr/bin/env python3
"""Heuristic static regression guard, not a PowerShell 2 parser or runtime test."""
from pathlib import Path
import re
root = Path(__file__).resolve().parent.parent
script = (root / 'windows/WinDoesNotSetup.ps1').read_text(encoding='utf-8-sig')
patterns = [r'\b(?:ConvertTo-Json|ConvertFrom-Json|Get-CimInstance|Get-FileHash|Invoke-WebRequest|Invoke-RestMethod)\b', r'\[ordered\]', r'(?i)\s-Raw\b|\s-NoNewline\b', r'\.[ \t]*(?:Where|ForEach)[ \t]*\(', r'\b(?:IsNullOrWhiteSpace|HasFlag|EnumerateFiles|CopyTo)\s*\(', r'\[(?:Tuple|Lazy)(?:\[|\])']
for pattern in patterns:
    assert not re.search(pattern, script, re.I), pattern
assert script.startswith('# WinDoesNot')
assert '-NoProfile -STA' in (root / 'windows/WinDoesNotSetup.cmd').read_text()
print('PASS legacy static patterns (not a runtime test)')
