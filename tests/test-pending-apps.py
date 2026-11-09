#!/usr/bin/env python3
"""Installer wishlist -> post-boot installation of deferred apps (Flatpak per user, repo/AUR via Store)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'iso/software'))
import install as installer  # noqa: E402

with tempfile.TemporaryDirectory() as temp:
    d = Path(temp)
    # 1. The installer records only IDs of deferred apps.
    base = d / 'base'; (base / 'iso/software').mkdir(parents=True)
    (base / 'iso/software/catalog.json').write_text((ROOT / 'iso/software/catalog.json').read_text())
    (base / 'offline-apps').mkdir()
    pending = d / 'var/pending-apps.json'
    installer.install_packages = lambda *a, **k: None
    installer.install_selection(['firefox', 'google-chrome', 'ollama'], 'en', base=base, record=d / 'var/profile.json', mode='offline', pending=pending)
    data = json.loads(pending.read_text())
    assert data == {'schema_version': 1, 'pending': ['google-chrome', 'ollama']}, data
    (base / 'offline-apps').mkdir()
    installer.install_selection(['firefox'], 'en', base=base, record=d / 'var/profile.json', mode='offline', pending=pending)
    assert not pending.exists(), 'no deferred apps: no wishlist'

    # 2. The runner: Flatpak per user, nothing arbitrary, repo/AUR only announced (once).
    pending.write_text(json.dumps({'schema_version': 1, 'pending': ['google-chrome', 'ollama', 'codex-cli', 'bogus', 'firefox']}))
    bin_dir = d / 'bin'; bin_dir.mkdir(); calls = d / 'calls'; notes = d / 'notes'
    (bin_dir / 'flatpak').write_text(f'#!/bin/sh\necho "flatpak $@" >> {calls}\n')
    (bin_dir / 'nm-online').write_text('#!/bin/sh\nexit 0\n')
    (bin_dir / 'notify-send').write_text(f'#!/bin/sh\necho "$@" >> {notes}\n')
    for f in bin_dir.iterdir(): f.chmod(0o755)
    env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'WINDOESNOT_PENDING': str(pending), 'XDG_STATE_HOME': str(d / 'state'),
           'WINDOESNOT_BASE': str(base), 'LANG': 'en_US.UTF-8'}
    tool = str(ROOT / 'desktop/bin/windoesnot-pending-apps')
    subprocess.run([tool, '--no-wait'], env=env, check=True)
    lines = calls.read_text().splitlines()
    assert lines == ['flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo',
                     'flatpak install --user --noninteractive -y flathub com.google.Chrome'], lines
    text = notes.read_text()
    assert 'Google Chrome' in text and 'Ollama, Codex CLI' in text and 'bogus' not in text and 'Firefox' not in text, text
    # Second run: Chrome is done, Ollama/Codex were already announced: nothing happens.
    calls.unlink(); notes.unlink()
    subprocess.run([tool, '--no-wait'], env=env, check=True)
    assert not calls.exists() and not notes.exists()
print('PASS pending-apps')

# 3. Web apps: per-user launchers, Chromium app mode when a Chromium-family browser exists, else Firefox; idempotent.
with tempfile.TemporaryDirectory() as temp:
    d = Path(temp); home = d / 'home'; home.mkdir()
    pend = d / 'pending.json'; pend.write_text(json.dumps({'schema_version': 1, 'pending': ['netflix', 'youtube', 'evil-site', 'gta2-rtx-remix-guide']}))
    bins = d / 'bin'; bins.mkdir()
    for name in ('notify-send', 'nm-online'): (bins / name).write_text('#!/bin/sh\nexit 0\n'); (bins / name).chmod(0o755)
    env = {**os.environ, 'HOME': str(home), 'PATH': str(bins), 'WINDOESNOT_PENDING': str(pend), 'XDG_STATE_HOME': str(home / 's'), 'LANG': 'en_US.UTF-8'}
    env.pop('WINDOESNOT_BASE', None)
    tool = str(ROOT / 'desktop/bin/windoesnot-pending-apps')
    desktop = home / '.local/share/applications/windoesnot-webapp-netflix.desktop'
    subprocess.run([sys.executable, tool, '--no-wait'], env=env, check=True)   # no browser in PATH: Firefox fallback
    text = desktop.read_text()
    assert '--new-window https://www.netflix.com/' in text and 'StartupWMClass=windoesnot-webapp-netflix' in text and 'Icon=/' in text and 'X-WinDoesNot-WebApp=true' in text, text
    assert (home / '.local/share/applications/windoesnot-webapp-youtube.desktop').is_file()
    assert not list((home / '.local/share/applications').glob('*evil*')), 'unknown ids never create launchers'
    guide = (home / '.local/share/applications/windoesnot-link-gta2-rtx-remix-guide.desktop').read_text()
    assert 'Exec=xdg-open https://github.com/Bennch/gta2-rtx-remix-linux' in guide and 'Categories=Game;' in guide, guide
    (bins / 'chromium').write_text('#!/bin/sh\n'); (bins / 'chromium').chmod(0o755)
    subprocess.run([sys.executable, tool, '--no-wait'], env=env, check=True)   # a Chromium browser appeared: rewritten
    text = desktop.read_text()
    assert f'Exec=chromium --app=https://www.netflix.com/ --user-data-dir={home}/.local/share/windoesnot/webapps/netflix' in text, text
    before = desktop.stat().st_mtime_ns
    subprocess.run([sys.executable, tool, '--no-wait'], env=env, check=True)   # nothing changed: untouched
    assert desktop.stat().st_mtime_ns == before
print('PASS pending-apps webapps')

# 4. Custom Flatpak remote (ArtCraft OCI): added per user from the catalogue allowlist, never from free text.
import copy  # noqa: E402
from catalog import load_catalog, flatpak_remote  # noqa: E402
catalog = load_catalog(ROOT / 'iso/software/catalog.json')
by_id = {a['id']: a for a in catalog['apps']}
assert flatpak_remote(catalog, by_id['krita'])[0] == 'flathub'
assert flatpak_remote(catalog, by_id['pdfcraft']) == ('artcraft-oci', 'https://getartcraft.com/artcraft-oci.flatpakrepo')
assert all(a['source'] == 'flatpak' and not a['packages'] for a in catalog['apps'] if a.get('flatpak_remote')), 'ArtCraft apps must stay deferred'
assert all((ROOT / 'iso/software/icons' / (i + '.png')).is_file() for i in ('artcraft-launcher', 'pdfcraft', 'photocraft', 'vectorcraft', 'filmcraft'))
for mutate in [lambda c: c['flatpak_remotes']['artcraft-oci'].update(url='http://getartcraft.com/x.flatpakrepo'),
               lambda c: c['flatpak_remotes']['artcraft-oci'].update(url='https://getartcraft.com/x.flatpakrepo; rm -rf ~'),
               lambda c: c['flatpak_remotes']['artcraft-oci'].update(url='oci+https://getartcraft.com'),
               lambda c: c['flatpak_remotes'].update({'flathub': {'url': 'https://evil.example/x.flatpakrepo'}}),
               lambda c: c['flatpak_remotes'].update({'Bad Name': {'url': 'https://a.example/x.flatpakrepo'}}),
               lambda c: next(a for a in c['apps'] if a['id'] == 'pdfcraft').update(flatpak_remote='unlisted'),
               lambda c: next(a for a in c['apps'] if a['id'] == 'ollama').update(flatpak_remote='artcraft-oci')]:
    broken = copy.deepcopy(catalog); mutate(broken)
    with tempfile.TemporaryDirectory() as tmp0:
        (Path(tmp0) / 'c.json').write_text(json.dumps(broken))
        try: load_catalog(Path(tmp0) / 'c.json')
        except ValueError: pass
        else: raise AssertionError('Unsafe Flatpak remote accepted')
with tempfile.TemporaryDirectory() as temp:
    d = Path(temp); pend = d / 'pending.json'
    pend.write_text(json.dumps({'schema_version': 1, 'pending': ['pdfcraft', 'artcraft-launcher', 'krita']}))
    bins = d / 'bin'; bins.mkdir()
    (bins / 'flatpak').write_text('#!/bin/sh\nexit 0\n'); (bins / 'flatpak').chmod(0o755)
    env = {**os.environ, 'PATH': f'{bins}:{os.environ["PATH"]}', 'WINDOESNOT_PENDING': str(pend), 'XDG_STATE_HOME': str(d / 's'), 'LANG': 'en_US.UTF-8'}
    env.pop('WINDOESNOT_BASE', None)
    out = subprocess.run([str(ROOT / 'desktop/bin/windoesnot-pending-apps'), '--dry-run', '--no-wait'], env=env, check=True, capture_output=True, text=True).stdout
    assert out.splitlines() == [
        'RUN: flatpak remote-add --user --if-not-exists artcraft-oci https://getartcraft.com/artcraft-oci.flatpakrepo',
        'RUN: flatpak install --user --noninteractive -y artcraft-oci ai.storyteller.pdfcraft',
        'RUN: flatpak remote-add --user --if-not-exists artcraft-oci https://getartcraft.com/artcraft-oci.flatpakrepo',
        'RUN: flatpak install --user --noninteractive -y artcraft-oci ai.storyteller.artcraft-launcher',
        'RUN: flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo',
        'RUN: flatpak install --user --noninteractive -y flathub org.kde.krita'], out
print('PASS pending-apps flatpak remote')
