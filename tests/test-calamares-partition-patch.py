#!/usr/bin/env python3
"""The Calamares partition patch must apply once, be idempotent and keep the C++ balanced."""
from pathlib import Path
import importlib.util
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'upstream/cachyos-calamares/src/modules/partition/gui/ChoicePage.cpp'
if not SOURCE.is_file():
    print('SKIP: upstream Calamares checkout missing')
    sys.exit(0)
spec = importlib.util.spec_from_file_location('patch_partition', ROOT / 'tools/patch-calamares-partition.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as directory:
    target = Path(directory) / 'ChoicePage.cpp'
    shutil.copy(SOURCE, target)
    assert module.patch_choicepage(target) is True
    patched = target.read_text()
    assert not module.patch_choicepage(target), 'second run must change nothing'
    assert target.read_text() == patched
    assert module.MARKER in patched and '#include <functional>' in patched
    assert 'canBeResized( candidate, Logger::Once() )' in patched and 'candidates == 1' in patched
    original = SOURCE.read_text()
    for opening, closing in ('{}', '()', '[]'):
        # Upstream strings and comments may contain stray brackets: compare the balance, not zero.
        assert (patched.count(opening) - patched.count(closing)) == (original.count(opening) - original.count(closing)), f'{opening}{closing} unbalanced by the patch'
    # The hint stays under its original source string so the translation catalogs still match.
    assert '"<strong>Select a partition to shrink, "' in patched
print('PASS: Calamares alongside patch applies once, is idempotent and balanced')
