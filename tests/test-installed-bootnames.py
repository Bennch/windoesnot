#!/usr/bin/env python3
"""Check the installed GRUB defaults without building an image."""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
tree = ast.parse((root / 'tools/prepare-profile.py').read_text())
configs = [node.args[1].value for node in ast.walk(tree)
           if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
           and node.func.id == 'write' and len(node.args) >= 2
           and isinstance(node.args[0], ast.BinOp)
           and isinstance(node.args[0].right, ast.Constant)
           and node.args[0].right.value == 'etc/default/grub.d/90-windoesnot.cfg'
           and isinstance(node.args[1], ast.Constant)]
assert len(configs) == 1
lines = configs[0].splitlines()
assert 'GRUB_DISTRIBUTOR="WinDoesNot"' in lines
assert 'GRUB_DISABLE_OS_PROBER=false' in lines
assert not any(line.startswith('GRUB_DISABLE_RECOVERY=') for line in lines)
print('PASS: installed GRUB distributor is branded and other OS detection remains enabled')
