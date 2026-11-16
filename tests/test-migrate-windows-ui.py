#!/usr/bin/env python3
"""Static guards for the legacy exporter's branded wizard (not a runtime test)."""
from pathlib import Path
import base64
import re

raw = (Path(__file__).resolve().parents[1] / 'windows/WinDoesNotSetup.ps1').read_bytes()
assert raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw
script = raw.decode('utf-8-sig')
ui = script[script.index('# The UI types'):]
for token in (
    'AutoScaleMode]::Dpi', 'System.Drawing.SizeF -ArgumentList 96,96',
    '$graphics.DpiX / 96.0', '$workArea.Width', '$workArea.Height',
    'System.Windows.Forms.FormStartPosition]::Manual', "'Segoe UI'", "'Tahoma'",
    'FromArgb(27,27,31)', 'FromArgb(20,20,20)', 'FromArgb(254,111,45)',
    'FromArgb(238,238,238)', 'FromArgb(170,170,170)',
    'GraphicsPath', 'SmoothingMode.AntiAlias', 'DoubleBuffered',
    'MouseOverBackColor', "'Top,Bottom,Left,Right'", "'Bottom,Right'",
    'GetHicon()', 'Icon]::FromHandle', 'DestroyIcon', '$script:form.Icon',
    "@('Willkommen','Auswahl','Fertig')", "@('Welcome','Selection','Done')",
    "'Auswahl speichern'", "'Save selection'", '$script:stepBars', '[char]0x2713',
    'Save-Handoff (Group-Selection $script:list.CheckedItems)',
):
    assert token in ui, token
assets = re.findall(r"\$(?:iconPng|logoPng) = '([^']+)'", ui)
assert len(assets) == 2 and sum(map(len, assets)) < 60 * 1024
for asset in assets:
    assert base64.b64decode(asset).startswith(b'\x89PNG\r\n\x1a\n')
assert ui.index('Save-Handoff (Group-Selection') < ui.index('$script:step++; Show-SetupStep')
print('PASS Windows exporter UI static guards (not a runtime or visual test)')
