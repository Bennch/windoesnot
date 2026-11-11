#!/usr/bin/env python3
"""Read-only release preflight. Temporary keyrings and sync databases stay in /tmp."""

import argparse
import base64
import configparser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OWN = ('store', 'device-manager', 'bluetooth', 'network', 'audio', 'graphics')
HIGHLIGHT = ('cachyos-calamares', 'cachyos-live-iso', 'snappy-switcher',
             'LACT', 'easyeffects', 'overskride', 'adw-network',
             'biglinux-driver-manager')
ORDER = {'PASS': 0, 'SKIP': 0, 'WARN': 1, 'FAIL': 2}


def command(*args, cwd=ROOT, timeout=20, env=None, check=True):
    result = subprocess.run(args, cwd=cwd, env=env, text=True,
                            capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[:300] or f'Exit {result.returncode}')
    return result


def git(*args, cwd=ROOT, timeout=15):
    return command('git', *args, cwd=cwd, timeout=timeout).stdout.strip()


def item(status, message):
    return status, message


def pin_date(name, pin):
    paths = [ROOT / 'upstream' / name, ROOT / name]
    for path in paths:
        if (path / '.git').exists():
            result = command('git', 'show', '-s', '--format=%ct', pin, cwd=path, check=False)
            if result.returncode == 0 and result.stdout.strip().isdigit():
                return int(result.stdout.strip())
    return None


def remote_head(url):
    lines = git('ls-remote', '--symref', url, 'HEAD', timeout=18).splitlines()
    ref = next((line.split()[2] for line in lines if line.startswith('ref:')), None)
    head = next((line.split()[0] for line in lines if line.endswith('\tHEAD') and not line.startswith('ref:')), None)
    if not head:
        raise RuntimeError('HEAD fehlt')
    return head, ref


def upstream(pins, offline):
    results = []
    for name, data in pins.items():
        if not isinstance(data, dict):
            continue
        if 'upstream' in data and 'upstream_commit' in data:
            url, pin = data['upstream'], data['upstream_commit']
            label = url.rstrip('/').split('/')[-1]
        elif 'url' in data and 'commit' in data and not name.startswith('windoesnot-'):
            url, pin, label = data['url'], data['commit'], name
        elif 'url' in data and 'version' in data and not name.startswith('windoesnot-'):
            results.append(item('WARN', f'{name}: Versionspin {data["version"]} ohne Commit, Drift nicht exakt prüfbar'))
            continue
        else:
            continue
        if offline:
            results.append(item('SKIP', f'{label}: Netzwerkprüfung offline'))
            continue
        try:
            head, ref = remote_head(url)
            if head == pin:
                results.append(item('PASS', f'{label}: Pin entspricht {ref or "HEAD"}'))
            else:
                old = pin_date(name, pin)
                days = f', Pin {max(0, (datetime.now(timezone.utc).timestamp() - old) // 86400):.0f} Tage alt' if old else ''
                marker = 'WICHTIG ' if label in HIGHLIGHT else ''
                results.append(item('WARN', f'{marker}{label}: HEAD {head[:12]} weicht von Pin {pin[:12]} ab{days}; Verlauf prüfen'))
        except Exception as exc:
            results.append(item('WARN', f'{label}: nicht erreichbar ({exc})'))
    return results


def own_pins(pins, offline):
    results = []
    for suffix in OWN:
        name = 'windoesnot-' + suffix
        data = pins[name]
        path = ROOT / data['path']
        pin = data['commit']
        if not (path / '.git').exists():
            results.append(item('WARN', f'{name}: lokaler Checkout fehlt'))
        else:
            head = git('rev-parse', 'HEAD', cwd=path)
            if git('status', '--porcelain', cwd=path):
                results.append(item('WARN', f'{name}: lokale Änderungen vorhanden'))
            if head == pin:
                results.append(item('PASS', f'{name}: Checkout auf Pin {pin[:12]}'))
            elif command('git', 'merge-base', '--is-ancestor', pin, head, cwd=path, check=False).returncode == 0:
                results.append(item('WARN', f'{name}: Checkout {head[:12]} ist weiter als Pin {pin[:12]}'))
            else:
                results.append(item('WARN', f'{name}: Checkout {head[:12]} liegt nicht auf Pin-Verlauf'))
            branch = 'master' if suffix == 'audio' else 'main'
            if not offline:
                try:
                    remote, _ = remote_head(data['url'])
                    # A remote may contain the pin on a non-default branch. Check all advertised refs,
                    # then use local ancestry only when the matching remote tip is available locally.
                    tips = {line.split()[0] for line in git('ls-remote', data['url'], 'refs/heads/*', timeout=18).splitlines()}
                    known = [tip for tip in tips if command('git', 'cat-file', '-e', tip,
                                                            cwd=path, check=False).returncode == 0]
                    present = pin in tips or any(command('git', 'merge-base', '--is-ancestor', pin, tip,
                                                        cwd=path, check=False).returncode == 0 for tip in known)
                    status = 'PASS' if present else 'WARN' if len(known) < len(tips) else 'FAIL'
                    results.append(item(status, f'{name}: Pin auf Remote vorhanden' if present else
                                        f'{name}: Pin auf Remote nicht nachweisbar' if status == 'FAIL' else
                                        f'{name}: Remote-Verlauf lokal unvollständig, Pin nicht sicher prüfbar'))
                    if head != remote and command('git', 'merge-base', '--is-ancestor', remote, head,
                                                  cwd=path, check=False).returncode == 0:
                        results.append(item('WARN', f'{name}: lokaler HEAD noch nicht auf Remote {branch}'))
                except Exception as exc:
                    results.append(item('WARN', f'{name}: Remote nicht erreichbar ({exc})'))
            else:
                results.append(item('SKIP', f'{name}: Remote-Prüfung offline'))
    return results


def published_sources(version):
    tag = 'v' + version
    if command('git', 'rev-parse', '-q', '--verify', 'refs/tags/' + tag, check=False).returncode == 0:
        return json.loads(git('show', f'{tag}:sources.json')), tag
    for commit in git('log', '--all', '--format=%H', '--', 'packaging/version.json').splitlines()[:100]:
        try:
            data = json.loads(git('show', f'{commit}:packaging/version.json'))
            if f'{data["version"]}-{data["release"]}' == version:
                return json.loads(git('show', f'{commit}:sources.json')), commit
        except Exception:
            continue
    return None, None


def versions(pins, offline):
    version = json.loads((ROOT / 'packaging/version.json').read_text())
    current = f'{version["version"]}-{version["release"]}'
    changelog = json.loads((ROOT / 'packaging/changelog.json').read_text())['releases'][0]
    results = [item('PASS' if changelog.get('version') == current and not changelog.get('unreleased') else 'FAIL',
                    f'Changelog: neuester Eintrag {changelog.get("version")} passt zu {current}'
                    if changelog.get('version') == current and not changelog.get('unreleased')
                    else f'Changelog: {current} fehlt als veröffentlichbarer neuester Eintrag')]
    if offline:
        return results + [item('SKIP', 'Öffentliches Paket-Repo offline')]
    try:
        with urlopen(Request('https://download.windoesnot.me/repo/x86_64/REPOSITORY.json', headers={'User-Agent': 'windoesnot-preflight'}), timeout=15) as response:
            public = json.load(response)['packages']
        core = public.get('windoesnot-desktop', {}).get('version')
        if not core:
            return results + [item('WARN', 'Öffentliches Repo enthält keine Desktop-Version')]
        old, ref = published_sources(core)
        if old is None:
            results.append(item('WARN', f'{core}: veröffentlichter sources.json-Stand im Git-Verlauf nicht ableitbar'))
        for suffix in OWN:
            name = 'windoesnot-' + suffix
            pkg = public.get(name, {}).get('version')
            if not pkg or old is None or name not in old:
                results.append(item('WARN', f'{name}: veröffentlichte Version oder Quell-Pin nicht ableitbar'))
                continue
            old_pin = old[name].get('commit')
            new_pin = pins[name]['commit']
            pkgbuild = ROOT / pins[name]['path'] / ('pkgbuild/PKGBUILD' if suffix == 'device-manager' else 'PKGBUILD')
            fields = dict(re.findall(r'^(pkgver|pkgrel)=([^\n]+)', pkgbuild.read_text(), re.M))
            local = f'{fields.get("pkgver", "?")}-{fields.get("pkgrel", "?")}'
            if old_pin != new_pin and local == pkg:
                results.append(item('WARN', f'{name}: Version nicht erhöht, Bestandssysteme bekommen die Änderung nicht ({pkg}, Pin {old_pin[:12]} → {new_pin[:12]})'))
            else:
                results.append(item('PASS', f'{name}: Quell-Pin und Paketversion geprüft ({local}, veröffentlicht {pkg})'))
        if old is not None and core == current:
            changed = command('git', 'diff', '--quiet', ref, 'HEAD', '--', 'desktop', 'tools', 'packaging', check=False).returncode
            results.append(item('WARN' if changed else 'PASS',
                                'Kernpakete: Version nicht erhöht, Bestandssysteme bekommen die Änderung nicht' if changed
                                else 'Kernpakete: keine Quelländerung seit veröffentlichtem Stand'))
        else:
            results.append(item('PASS', f'Kernpakete: lokal {current}, veröffentlicht {core}'))
    except Exception as exc:
        results.append(item('WARN', f'Öffentliches Paket-Repo nicht erreichbar ({exc})'))
    return results


def hyprland(pins, offline):
    results = []
    pin = pins['hyprland']['version']
    host = command('pacman', '-Q', 'hyprland', check=False).stdout.strip() if shutil.which('pacman') else ''
    host_version = host.split()[-1] if host else None
    norm = lambda value: re.sub(r'\.\d+$', '', value) if value else None
    results.append(item('PASS' if host_version and norm(host_version) == pin else 'WARN',
                        f'Hyprland Host {host_version or "nicht installiert"}, Pin {pin}'))
    if offline:
        results.append(item('SKIP', 'CachyOS Repo-Version offline'))
    elif shutil.which('pacman'):
        try:
            with tempfile.TemporaryDirectory(prefix='windoesnot-pacman-') as tmp:
                db = Path(tmp) / 'db'
                db.mkdir()
                command('pacman', '-Sy', '--dbpath', str(db), '--cachedir', tmp,
                        '--logfile', str(Path(tmp) / 'pacman.log'), timeout=45)
                info = command('pacman', '-Si', 'hyprland', '--dbpath', str(db), timeout=15).stdout
                match = re.search(r'^Version\s*:\s*(\S+)', info, re.M)
                repo = match.group(1) if match else None
                results.append(item('PASS' if repo and norm(repo) == pin else 'WARN',
                                    f'Hyprland Repo {repo or "unbekannt"}, Pin {pin}'))
        except Exception as exc:
            results.append(item('WARN', f'Hyprland Repo nicht erreichbar ({exc})'))
    else:
        results.append(item('WARN', 'pacman fehlt, Repo-Version nicht prüfbar'))
    plugin_dir = Path.home() / '.config/hypr/plugins'
    for name in ('hyprbars.so', 'hyprdrag.so'):
        plugin = plugin_dir / name
        if not plugin.is_file():
            results.append(item('WARN', f'{name}: Host-Plugin fehlt; tools/build-components.sh'))
            continue
        try:
            test = command(sys.executable, str(ROOT / 'tools/check-plugin-symbols.py'), str(plugin), timeout=30, check=False)
            results.append(item('PASS' if test.returncode == 0 else 'WARN',
                                f'{name}: Symbolprüfung {"bestanden" if test.returncode == 0 else "fehlgeschlagen"}; '
                                'Ladetest im Desktop bleibt nötig' if test.returncode == 0 else
                                f'{name}: Symbolprüfung fehlgeschlagen; tools/build-components.sh'))
        except Exception as exc:
            results.append(item('WARN', f'{name}: Symbolprüfung nicht möglich ({exc}); tools/build-components.sh'))
    return results


def key_expiry(raw, label):
    now = datetime.now(timezone.utc).timestamp()
    rows = [line.split(':') for line in raw.splitlines()]
    keys = [row for row in rows if row[0] in ('pub', 'sub')]
    if not keys:
        return [item('WARN', f'{label}: kein Schlüssel lesbar')]
    result = []
    for row in keys:
        expiry = int(row[6]) if row[6].isdigit() else 0
        kind = 'Hauptschlüssel' if row[0] == 'pub' else 'Unterschlüssel'
        if not expiry:
            result.append(item('WARN', f'{label} {kind}: kein Ablaufdatum'))
            continue
        days = int((expiry - now) // 86400)
        status = 'FAIL' if days < 0 else 'WARN' if days < 90 else 'PASS'
        result.append(item(status, f'{label} {kind}: läuft in {days} Tagen ab'))
    return result


def keys(_pins, _offline):
    results = []
    if not shutil.which('gpg'):
        return [item('WARN', 'gpg fehlt, Schlüssel-Fristen nicht prüfbar')]
    with tempfile.TemporaryDirectory(prefix='windoesnot-gpg-') as home:
        os.chmod(home, 0o700)
        env = dict(os.environ, GNUPGHOME=home)
        signing = ROOT / 'packaging/release-key/RELEASE-KEY.asc'
        command('gpg', '--batch', '--import', str(signing), env=env, check=False)
        listing = command('gpg', '--batch', '--with-colons', '--list-keys', env=env, check=False)
        if not any(line.startswith('pub:') for line in listing.stdout.splitlines()):
            results.append(item('WARN', 'Signierschlüssel nicht importierbar'))
        else:
            results += key_expiry(listing.stdout, 'Release')
        cfg = configparser.ConfigParser()
        cfg.read(ROOT / 'iso/flatpak/flathub.flatpakrepo')
        raw = base64.b64decode(cfg['Flatpak Repo']['GPGKey'])
        flat = subprocess.run(['gpg', '--batch', '--import'], input=raw, env=env,
                              capture_output=True, timeout=15)
        fingerprint = '6E5C05D979C76DAF93C081354184DD4D907A7CAE'
        selected = command('gpg', '--batch', '--with-colons', '--list-keys', fingerprint,
                           env=env, check=False)
        if not any(line.startswith('pub:') for line in selected.stdout.splitlines()):
            results.append(item('WARN', 'Flathub-Schlüssel nicht importierbar'))
        else:
            results += key_expiry(selected.stdout, 'Flathub')
    return results


def security(_pins, _offline):
    if not shutil.which('arch-audit'):
        return [item('WARN', 'arch-audit nicht installiert, Sicherheitsprüfung manuell nachholen')]
    images = sorted((ROOT / 'build').glob('*/work/x86_64/airootfs/var/lib/pacman/local'),
                    key=lambda p: p.stat().st_mtime, reverse=True)
    if images:
        # arch-audit has no portable image database flag. Avoid claiming to scan the image.
        target = f'Host; Image {images[0].parents[6].name} separat prüfen'
    else:
        target = 'Host; kein Image mit Paketdatenbank vorhanden'
    run = command('arch-audit', timeout=30, check=False)
    if run.returncode:
        return [item('WARN', f'arch-audit ({target}) konnte nicht ausgewertet werden: {(run.stderr or run.stdout).strip()[:180]}')]
    lines = [line for line in run.stdout.splitlines() if line.strip()]
    return [item('WARN' if lines else 'PASS', f'arch-audit ({target}): {len(lines)} gemeldete Einträge')]


def repo_state(pins, offline):
    results = []
    for name, path in (('Hauptrepo', ROOT), ('website', ROOT / 'website')):
        if not (path / '.git').exists():
            results.append(item('WARN', f'{name}: kein Git-Checkout'))
            continue
        branch = git('branch', '--show-current', cwd=path)
        results.append(item('PASS' if branch == 'main' else 'WARN', f'{name}: Branch {branch or "detached"}'))
        status = git('status', '--porcelain', cwd=path)
        results.append(item('PASS' if not status else 'WARN', f'{name}: {"sauber" if not status else "lokale Änderungen"}'))
        upstream_ref = command('git', 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}', cwd=path, check=False)
        if upstream_ref.returncode:
            results.append(item('WARN', f'{name}: kein Tracking-Branch'))
        else:
            ahead = git('rev-list', '--count', f'{upstream_ref.stdout.strip()}..HEAD', cwd=path)
            results.append(item('WARN' if ahead != '0' else 'PASS', f'{name}: {ahead} Commits vor lokal bekanntem Remote-Stand'))
            if offline:
                results.append(item('SKIP', f'{name}: Remote-Stand offline nicht aktualisiert'))
            else:
                try:
                    remote_name = upstream_ref.stdout.strip().split('/', 1)[0]
                    url = git('remote', 'get-url', remote_name, cwd=path)
                    refs = git('ls-remote', url, 'refs/heads/main', cwd=path, timeout=18).splitlines()
                    remote_head = refs[0].split()[0] if refs else None
                    local_head = git('rev-parse', 'HEAD', cwd=path)
                    results.append(item('PASS' if remote_head == local_head else 'WARN',
                                        f'{name}: HEAD auf Remote main' if remote_head == local_head else
                                        f'{name}: HEAD weicht von Remote main ab'))
                except Exception as exc:
                    results.append(item('WARN', f'{name}: Remote nicht erreichbar ({exc})'))
    version = json.loads((ROOT / 'packaging/version.json').read_text())
    current = f'{version["version"]}-{version["release"]}'
    previous = f'{version["version"]}-{int(version["release"])-1}'
    files = [*(ROOT / 'website/content').rglob('*'), ROOT / 'website/tools/build-site.py']
    texts = [p.read_text(errors='replace') for p in files if p.is_file() and p.suffix in ('.json', '.html', '.py', '.md')]
    found = sum(current in text for text in texts)
    old = sum(previous in text for text in texts)
    results.append(item('WARN' if old or not found else 'PASS',
                        f'Webseite: aktuelle Version in {found} Dateien, Vorversion in {old} Dateien'))
    return results


def cleanup(_pins, _offline):
    results = []
    total = 0
    complete = True
    for name in ('build', 'out', 'vm'):
        path = ROOT / name
        if not path.exists():
            continue
        du = command('du', '-s', '-B1', str(path), timeout=90, check=False)
        size = int(du.stdout.split()[0]) if du.stdout.split() and du.stdout.split()[0].isdigit() else 0
        complete &= du.returncode == 0
        total += size
        results.append(item('PASS' if du.returncode == 0 else 'WARN',
                            f'{name}/: {size / 2**30:.1f} GiB' if du.returncode == 0 else
                            f'{name}/: Größe wegen Leserechten nicht vollständig messbar'))
        if name == 'build':
            dirs = [p for p in path.iterdir() if p.is_dir() and re.match(r'^\d{8}-\d{6}', p.name)]
        elif name == 'out':
            dirs = [p for p in path.iterdir() if p.is_dir() and re.match(r'^\d{8}-\d{6}', p.name)]
        else:
            dirs = [p for p in path.iterdir() if p.is_dir() and (p / 'disk.qcow2').exists()]
        results.append(item('WARN' if len(dirs) > 3 else 'PASS', f'{name}/: {len(dirs)} Build-, ISO- oder VM-Ordner gleicher Art'))
    results.append(item('WARN' if total > 200 * 10**9 or not complete else 'PASS',
                        f'build/, out/, vm/ zusammen mindestens {total / 2**30:.1f} GiB' if not complete else
                        f'build/, out/, vm/ zusammen {total / 2**30:.1f} GiB'))
    free = shutil.disk_usage(ROOT).free
    results.append(item('WARN' if free < 100 * 10**9 else 'PASS', f'Freier Platz {free / 2**30:.1f} GiB'))
    return results


CHECKS = [('python3', 'tools/validate-desktop.py'),
          ('python3', 'tests/test-icon-map-startup.py'),
          ('python3', 'tests/test-lua-placement.py'),
          ('python3', 'tools/sync-branding.py', '--check'),
          ('python3', 'tests/test-branding.py'),
          ('python3', 'tests/test-appearance-loader.py'),
          ('python3', 'tests/test-software.py'),
          ('python3', 'tests/test-install-modes.py'),
          ('./build-and-run.sh', '--dry-run')]


def standard(_pins, _offline):
    results = []
    for args in CHECKS:
        try:
            run = command(*args, timeout=120, check=False)
            output = (run.stderr + '\n' + run.stdout).lower()
            if run.returncode == 0:
                status = 'PASS'
            elif re.search(r'(cannot open display|no display|could not connect to display|cannot connect to dbus|failed to connect to bus|dbus.*unavailable)', output):
                status = 'SKIP'
            else:
                status = 'FAIL'
            results.append(item(status, f'{" ".join(args)}: {"ok" if status == "PASS" else (run.stderr or run.stdout).strip()[-180:]}'))
        except Exception as exc:
            results.append(item('FAIL', f'{" ".join(args)}: {exc}'))
    return results


GROUPS = ((1, 'Upstream-Drift', upstream), (2, 'Unterprojekt-Pins', own_pins),
          (3, 'Versionen', versions), (4, 'Hyprland und Plugins', hyprland),
          (5, 'Schlüssel und Fristen', keys), (6, 'Sicherheit', security),
          (7, 'Repo und Webseite', repo_state), (8, 'Aufräumen', cleanup),
          (9, 'Standardprüfungen', standard))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Netzwerkprüfungen überspringen')
    parser.add_argument('--only', help='Prüfnummern, z. B. 1,3,5')
    parser.add_argument('--markdown', type=Path, help='Bericht zusätzlich als Markdown schreiben')
    args = parser.parse_args()
    try:
        selected = set(range(1, 10)) if not args.only else {int(x) for x in args.only.split(',')}
    except ValueError:
        parser.error('--only erwartet kommaseparierte Nummern 1 bis 9')
    if not selected.issubset(set(range(1, 10))):
        parser.error('--only erlaubt nur Nummern 1 bis 9')
    pins = json.loads((ROOT / 'sources.json').read_text())
    lines = [f'# Release-Preflight {datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")}', '']
    failed = False
    for number, title, func in GROUPS:
        if number not in selected:
            continue
        try:
            entries = func(pins, args.offline)
        except Exception as exc:
            entries = [item('FAIL', f'Prüfung abgebrochen: {exc}')]
        state = max((status for status, _ in entries), key=lambda x: ORDER[x], default='PASS')
        failed |= state == 'FAIL'
        lines.append(f'## {number}. {title}: {state}')
        lines.extend(f'- {status}: {message}' for status, message in entries)
        lines.append('')
    lines += ['## 10. Testlücken',
              '- HINWEIS: Vollständige Installationsmatrix zuletzt mit 0.1.0-18. AMD ungetestet. Update-Weg in einer VM testen.', '']
    report = '\n'.join(lines)
    print(report)
    if args.markdown:
        args.markdown.write_text(report + '\n')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
