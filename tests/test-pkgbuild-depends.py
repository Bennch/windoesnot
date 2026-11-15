#!/usr/bin/env python3
"""depends arrays in the PKGBUILD template must be closed on their own line, without stray tokens or duplicates."""
import re
from pathlib import Path
text = (Path(__file__).resolve().parents[1] / 'packaging/PKGBUILD.in').read_text()
for m in re.finditer(r'^ *depends=\((.*)$', text, re.M):
    line = m[1]
    assert line.rstrip().endswith(')') and line.count(')') == 1, 'stray tokens after the closing parenthesis: ' + line[-60:]
    tokens = re.findall(r'"[^"]*"|[^\s")]+', line.rstrip()[:-1])
    dupes = {t for t in tokens if tokens.count(t) > 1}
    assert not dupes, 'duplicate dependencies: ' + ', '.join(sorted(dupes))
loop = text[text.index('for command in desktop/bin/*'):]
loop = loop[:loop.index('done')]
assert 'ghostty' in loop and 'continue' in loop, 'desktop/bin/ghostty must not be installed to /usr/bin (conflicts with the ghostty package)'
print('PASS: PKGBUILD depends arrays are well formed and the ghostty wrapper stays out of /usr/bin')

# The package must never own /usr/local/bin/ghostty: older releases copied an unowned file there and
# pacman aborts an update with a file conflict. A scriptlet installs the shim instead.
import subprocess
pkgbuild = (Path(__file__).resolve().parent.parent / 'packaging/PKGBUILD.in').read_text()
assert '$pkgdir/usr/local/bin/ghostty' not in pkgbuild
assert '$pkgdir/usr/lib/windoesnot/ghostty-wrapper' in pkgbuild and 'install=windoesnot-desktop.install' in pkgbuild
scriptlet = Path(__file__).resolve().parent.parent / 'packaging/windoesnot-desktop.install'
assert subprocess.run(['bash', '-n', str(scriptlet)]).returncode == 0
text = scriptlet.read_text()
assert 'post_install' in text and 'post_upgrade' in text and 'pre_remove' in text and '/usr/local/bin/ghostty' in text
print('PASS: desktop package ships the Ghostty wrapper via scriptlet, no /usr/local/bin file conflict')
