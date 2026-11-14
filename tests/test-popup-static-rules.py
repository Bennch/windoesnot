#!/usr/bin/env python3
"""Battery and nearby popups are placed by a static, size independent rule (no Python bridge on open)."""
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ref = (ROOT / 'desktop/config/hypr/lua/reference.lua').read_text()
qml = (ROOT / 'desktop/config/quickshell/default/shell.qml').read_text()
for name in ('battery-config', 'nearby-config', 'weather-popup-config'):
    m = re.search(r'\["name"\]="%s",\["move"\]=\{"([^"]+)","([^"]+)"\}' % name, ref)
    assert m, name + ' has no static move rule'
    assert 'monitor_w' in m[1] and 'window_w' in m[1] and 'monitor_h' in m[2] and 'window_h' in m[2], m.groups()
    assert '["center"]' not in ref[ref.index('["name"]="%s"' % name):ref.index('["name"]="%s"' % name) + 300]
assert not re.search(r'windowrule\[(battery|nearby|weather-popup)-config\]', qml), 'popups must not set rules through the Python bridge on open'
assert 'hl.dsp.window.move' in qml
assert 'title:^(quickshell-weather)$' in qml and 'weatherPlaceTimer' in qml
print('PASS: battery, nearby and weather popups use static expression rules and native hyprctl placement')
