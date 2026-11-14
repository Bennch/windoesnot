#!/usr/bin/env python3
"""Battery, nearby and weather popups are placed by a static, size independent rule at map time.

Verified live on Hyprland 0.57.1: the window appears at its final position (right edge,
flush above the 45 px taskbar) and never moves; fixed numbers would leave it off by the
difference between the rule's and the real height.
"""
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ref = (ROOT / 'desktop/config/hypr/lua/reference.lua').read_text()
qml = (ROOT / 'desktop/config/quickshell/default/shell.qml').read_text()
geo = (ROOT / 'desktop/config/hypr/lua/bin/display_geometry.py').read_text()
for name in ('battery-config', 'nearby-config', 'weather-popup-config'):
    block = ref[ref.index('["name"]="%s"' % name):ref.index('["name"]="%s"' % name) + 260]
    m = re.search(r'\["move"\]=\{"([^"]+)","([^"]+)"\}', block)
    assert m, name + ' has no static move rule'
    assert 'monitor_w' in m[1] and 'window_w' in m[1] and 'monitor_h' in m[2] and 'window_h' in m[2], m.groups()
    assert '["no_anim"]=true' in block and '["center"]' not in block, name
    assert "'%s'" % name not in geo, name + ' must not get fixed numbers from the generated geometry'
assert '["size"]="380 390"' not in ref[ref.index('["name"]="weather-popup-config"'):ref.index('["name"]="weather-popup-config"') + 300]
assert not re.search(r'windowrule\[(battery|nearby|weather-popup)-config\]', qml), 'popups must not set rules through the Python bridge on open'
assert 'hl.dsp.window.move' in qml and 'hl.dsp.window.resize' in qml, 'popups are resized to their content, then moved'
assert 'popupFitCommand("quickshell-weather"' in qml and 'popupFitCommand("quickshell-battery"' in qml and 'popupFitCommand("quickshell-nearby"' in qml
assert 'weatherPopupIconItem.mapToItem' in qml, 'the weather popup is centred over its taskbar icon'
assert 'opacity: weatherPopup.placed ? 1 : 0' in qml, 'the weather popup stays invisible until it has been moved'
assert 'target: "windoesnot-weather"' in qml
print('PASS: battery, nearby and weather popups use static expression rules and native hyprctl placement')
