#!/usr/bin/env python3
"""Static guards for the legacy exporter's DPI-aware, branded layout."""
from pathlib import Path

raw = (Path(__file__).resolve().parents[1] / 'windows/WinDoesNotSetup.ps1').read_bytes()
assert raw.startswith(b'\xef\xbb\xbf') and b'\r' not in raw
script = raw.decode('utf-8-sig')
ui = script[script.index('$form = New-Object System.Windows.Forms.Form'):]
for token in (
    'AutoScaleMode]::Dpi', 'System.Drawing.SizeF -ArgumentList 96,96',
    '$graphics.DpiX / 96.0', '$form.AutoScroll = $true',
    '[Math]::Min($form.Width, $workArea.Width)', '[Math]::Min($form.Height, $workArea.Height)',
    'System.Windows.Forms.FormStartPosition]::Manual', "'Segoe UI'", "'Tahoma'", '9.5',
    'FromArgb(27,27,31)', 'FromArgb(20,20,20)', 'FromArgb(254,111,45)',
    'FromArgb(238,238,238)', '$save.FlatStyle', 'FlatAppearance.BorderColor',
    'FlatAppearance.MouseOverBackColor', 'FlatAppearance.MouseDownBackColor',
    '$save.UseVisualStyleBackColor = $false', '$wifi.FlatStyle',
    '$intro.AutoSize = $false', '$notice.AutoSize = $false',
    "'Save selection'", 'Source: $shownLabel', 'Export saved Wi-Fi keys',
):
    assert token in ui, token
assert 'System.Drawing.Color]::White' not in ui
print('PASS Windows exporter UI static guards (not a runtime or visual test)')
