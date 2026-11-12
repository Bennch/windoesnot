#!/usr/bin/env python3
"""Pure-logic checks for the hyprdesk file exchange (clipboard formats, collision names, safe recursive copy)."""
import importlib.util
import os
import sys
import tempfile
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'desktop/config/hyprdesk/hyprdesk.py'

with tempfile.TemporaryDirectory(prefix='windoesnot-hyprdesk-test-') as temporary:
    work = Path(temporary)
    home = work / 'home'
    home.mkdir()
    os.environ['HOME'] = str(home)  # the module creates ~/.config/hyprdesk on import
    os.environ['XDG_CONFIG_HOME'] = str(home / '.config')
    spec = importlib.util.spec_from_file_location('hyprdesk_under_test', SOURCE)
    hd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hd)

    # Monitor identity must survive HiDPI, rotation and different desktop offsets.
    monitor = SimpleNamespace(get_connector=lambda: 'Unknown-1')
    assert hd.get_monitor_connector_name(monitor) == 'Unknown-1'
    for transform in (0, 1, 5):
        geo = SimpleNamespace(x=9, y=2, width=1512, height=945)
        mon = {'name':'Unknown-1', 'x':9, 'y':2, 'width':3024,
               'height':1890, 'scale':2, 'transform':transform}
        if transform % 2:
            mon['width'], mon['height'] = mon['height'], mon['width']
        monitor = SimpleNamespace(get_connector=lambda: None, get_geometry=lambda: geo)
        with patch.object(hd.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps([mon]))):
            assert hd.get_monitor_connector_name(monitor) == 'Unknown-1'

    # Old logical fallback IDs merge into the connector ID without losing
    # icons, regardless of the order in which they were saved.
    mon = {'name':'Unknown-1', 'x':9, 'y':2, 'width':3024, 'height':1890, 'scale':2, 'transform':0}
    for saved in ({'9_2_1512_945': {'icons':[{'name':'Old'}]}, 'Unknown-1': {'icons':[{'name':'Papierkorb'}]}},
                  {'Unknown-1': {'icons':[{'name':'Papierkorb'}]}, '9_2_1512_945': {'icons':[{'name':'Old'}]}}):
        app = SimpleNamespace(global_state={'monitors': saved})
        with patch.object(hd.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps([mon]))), \
             patch.object(hd, 'save_state', lambda state: None):
            hd.HyprDeskApp.migrate_old_monitor_ids(app, None, 1)
        monitors = app.global_state['monitors']
        assert list(monitors) == ['Unknown-1'], monitors
        assert sorted(i['name'] for i in monitors['Unknown-1']['icons']) == ['Old', 'Papierkorb']

    # --- collision names
    taken = {'a.txt', 'a (2).txt', 'dir', 'dir (2)', 'x.tar.gz', '.bashrc'}
    ex = taken.__contains__
    assert hd.unique_name('fresh.txt', ex) == 'fresh.txt'
    assert hd.unique_name('a.txt', ex) == 'a (3).txt'
    assert hd.unique_name('a (2).txt', ex) == 'a (3).txt'
    assert hd.unique_name('dir', ex, True) == 'dir (3)'
    assert hd.unique_name('x.tar.gz', ex) == 'x (2).tar.gz'
    assert hd.unique_name('.bashrc', ex) == '.bashrc (2)'
    assert hd.unique_name('v1.2', {'v1.2'}.__contains__, True) == 'v1.2 (2)'

    # --- URIs
    assert hd.uri_to_path('file:///home/x/a%20b%C3%A4.txt') == Path('/home/x/a bä.txt')
    assert hd.uri_to_path('file://localhost/tmp/x') == Path('/tmp/x')
    for bad in ('http://example.org/a', 'file://otherhost/tmp/x', 'smb://h/s', 'file:///a%00b', 'relative/path', ''):
        assert hd.uri_to_path(bad) is None, bad
    got = hd.parse_uri_list('# c\r\nfile:///tmp/a%20b\r\n\r\nhttp://x/y\r\nfile:///tmp/c\n')
    assert got == [Path('/tmp/a b'), Path('/tmp/c')], got

    # --- gnome-copied-files round trip with spaces, umlauts, percent and hash signs
    paths = [Path('/home/u/Schreibtisch/Ärger & Ö 100%.txt'), Path('/tmp/a b/#x')]
    for action in ('copy', 'cut'):
        text = hd.build_gnome_copied(action, paths)
        assert text.startswith(action + '\nfile:///'), text
        assert hd.parse_gnome_copied(text) == (action, paths)
        assert hd.parse_gnome_copied(text.encode()) == (action, paths)
    assert hd.parse_gnome_copied('file:///tmp/a') == ('copy', [Path('/tmp/a')])
    assert hd.parse_gnome_copied('link\nfile:///tmp/a')[0] == 'copy'
    assert hd.parse_uri_list(hd.build_uri_list(paths)) == paths

    # --- transfer checks
    desktop = work / 'Schreibtisch'
    desktop.mkdir()
    tree = work / 'Quelle Ördner'
    (tree / 'sub dir').mkdir(parents=True)
    (tree / 'sub dir' / 'datei ä.txt').write_text('inhalt')
    (tree / 'top.txt').write_text('top')
    os.symlink('top.txt', tree / 'link-to-top')
    os.symlink('/nonexistent/target', tree / 'dangling')
    os.symlink('sub dir', tree / 'link-to-dir')
    assert hd.transfer_problem(work / 'nope', desktop) == 'missing'
    assert hd.transfer_problem(tree, tree / 'sub dir') == 'self'
    assert hd.transfer_problem(tree, tree) == 'self'
    assert hd.transfer_problem(tree, desktop) is None
    assert hd.transfer_problem(tree / 'top.txt', tree) is None            # copy next to itself -> 'top (2).txt'
    assert hd.transfer_problem(tree / 'top.txt', tree, move=True) == 'same'
    assert hd.transfer_problem(tree / 'link-to-dir', tree / 'sub dir') is None  # a link may be copied anywhere

    # --- recursive copy keeps symlinks as symlinks and never follows them
    dst = desktop / 'copy'
    hd.copy_tree(str(tree), str(dst))
    assert (dst / 'sub dir' / 'datei ä.txt').read_text() == 'inhalt'
    assert os.readlink(dst / 'link-to-top') == 'top.txt'
    assert os.readlink(dst / 'dangling') == '/nonexistent/target'
    assert (dst / 'link-to-dir').is_symlink() and os.readlink(dst / 'link-to-dir') == 'sub dir'

    # --- copy and move via the temp name used by the worker thread
    tmp = hd.temp_path_for(desktop, 'Quelle Ördner', 0)
    assert tmp.name.startswith('.') and tmp.name.endswith('.wdn-part')
    hd.transfer_to_temp(str(tree), str(tmp), move=False)
    assert tree.exists() and (tmp / 'top.txt').exists()
    moved = work / 'moved'
    hd.transfer_to_temp(str(tmp), str(moved), move=True)
    assert not tmp.exists() and (moved / 'sub dir' / 'datei ä.txt').exists()
    # a failing copy leaves no half-finished temp behind
    bad = work / 'exists-already'
    bad.mkdir()
    try:
        hd.transfer_to_temp(str(tree), str(bad), move=False)
    except OSError:
        pass
    else:
        raise AssertionError('copy onto an existing path must fail')

    # --- texts in both languages
    for key in ('copy', 'cut', 'paste', 'transfer_failed', 'transfer_self', 'transfer_missing'):
        assert hd.tr(key, 'de') != key and hd.tr(key, 'en') != key
    assert hd.tr('paste', 'de') == 'Einfügen' and hd.tr('cut', 'en') == 'Cut'

print('hyprdesk file exchange logic OK')
