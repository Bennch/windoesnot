#!/usr/bin/env python3
"""Check that a plugin's strong imports exist in the target compositor or its libraries.

Run inside the build container. This does not load the plugin and cannot replace
a compositor runtime test.
"""

from pathlib import Path
import re
import subprocess
import sys


def symbols(path: Path, undefined: bool = False) -> set[str]:
    mode = '--undefined-only' if undefined else '--defined-only'
    output = subprocess.check_output(['nm', '-D', mode, str(path)], text=True)
    result = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2 or (undefined and fields[-2] != 'U'):
            continue
        result.add(fields[-1].split('@')[0])
    return result


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit('Usage: check-plugin-symbols.py /work/path/to/plugin.so')

    compositor = Path('/usr/bin/Hyprland')
    plugin = Path(sys.argv[1])
    dependencies = subprocess.check_output(['ldd', str(compositor)], text=True)
    libraries = {Path(p) for p in re.findall(r'(/[^\s()]+)', dependencies)}
    libraries.add(compositor)
    # The compiler adds runtime dependencies to the plugin too.
    plugin_dependencies = subprocess.check_output(['ldd', str(plugin)], text=True)
    libraries.update(Path(p) for p in re.findall(r'(/[^\s()]+)', plugin_dependencies))

    available = set()
    for library in libraries:
        if library.is_file():
            available.update(symbols(library))

    required = symbols(plugin, undefined=True)
    missing = sorted(required - available)
    if missing:
        print(f'FAIL: {len(missing)} unresolved strong imports in {plugin}')
        print(subprocess.check_output(['c++filt', *missing], text=True), end='')
        return 1

    print(f'PASS: {len(required)} strong imports in {plugin} are exported by the target or its libraries.')
    print('This is a symbol check, not a plugin load or desktop behavior test.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
