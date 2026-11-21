#!/usr/bin/env python3
"""syncFocusGrab remembers the wish per grab: a later close cancels the pending arming (Store X needed a second click after
'Uninstall...' because the stale callLater re-armed the Start menu grab after it was closed)."""
from pathlib import Path
import re

source = (Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default/shell.qml').read_text()
match = re.search(r'function syncFocusGrab\(grab, vis\) \{.*?\n    \}\n', source, re.S)
assert match, 'syncFocusGrab missing'
body = match.group(0)
assert 'entry.vis = vis' in body and 'Qt.callLater(function() { if (entry.vis) grab.active = true })' in body, body
assert 'else grab.active = false' in body
assert 'Qt.callLater(function() { grab.active = true })' not in source, 'unconditional arming is back'
print('PASS: focus grab arming honours the latest wish (no stale re-arm after a close)')
