#!/usr/bin/env python3
"""The technical flag must survive every step from windoesnot-list-apps to the Start menu delegate."""
import re
from pathlib import Path
Q = Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default'
shell = (Q / 'shell.qml').read_text()
replace = (Q / 'replace.qml').read_text()
# applyOverride rebuilds the entry from known fields and must copy technical too.
apply = replace[replace.index('function applyOverride'):]
assert re.search(r'technical:\s*appData\.technical\s*===\s*true', apply), 'applyOverride drops the technical flag'
# A ListModel only knows the roles of its first element: every append source must define technical.
assert re.search(r'customAppData\s*=\s*\{[^}]*technical:\s*false', shell, re.S), 'custom apps need technical: false'
assert re.search(r'allAppsModel\.append\(\{[^}]*technical:', shell, re.S), 'rebuildModel must keep technical'
assert 'model.technical !== true' in shell, 'delegate must read the role through model (no ReferenceError)'
# The toggle sits next to the app count, not over the search input.
assert 'id: appCountLabel' in shell and 'anchors.right: appCountLabel.left' in shell
print('PASS: technical apps stay flagged through the model and the toggle does not cover the search field')
