# SPDX-License-Identifier: GPL-3.0-or-later
"""Copy selected Windows data after Calamares creates the target user."""
import json
from pathlib import Path
import re
import sys
import subprocess
import tempfile
import os
import libcalamares

sys.path.insert(0, '/usr/lib/windoesnot')
import migrate


def nice_windows_name(raw):
    """'Windows 10 19045' (PowerShell exporter) or '10.0.26100.0' (Setup app) -> 'Windows 10' / 'Windows 11'."""
    numeric = re.match(r'^(\d+)\.(\d+)\.(\d+)', raw)
    if numeric:
        major, minor, build = (int(part) for part in numeric.groups())
        if major == 10:
            return 'Windows 11' if build >= 22000 else 'Windows 10'
        return {(6, 3): 'Windows 8.1', (6, 2): 'Windows 8', (6, 1): 'Windows 7'}.get((major, minor), 'Windows')
    return re.sub(r'^(Windows [0-9.]+).*$', r'\1', raw)


def pretty_name():
    return 'Daten kopieren' if str(libcalamares.globalstorage.value('locale')).startswith('de') else 'Copy data'


def run():
    # The result page must only report a transfer after the copy job actually
    # completed; the presence of a selection alone is not proof of a copy.
    libcalamares.globalstorage.insert('windoesnotMigrateCompleted', False)
    libcalamares.globalstorage.insert('windoesnotMigrateWarning', '')
    libcalamares.globalstorage.insert('windoesnotMigrateSystem', '')
    german = str(libcalamares.globalstorage.value('locale')).startswith('de')
    raw = libcalamares.globalstorage.value('windoesnotMigrateManifest')
    def warn(message, shown=None):
        # The log stays English; the result page shows the localised text.
        libcalamares.globalstorage.insert('windoesnotMigrateWarning', shown or message)
        libcalamares.utils.warning('windoesnotmigrate: ' + message)
    try:
        if not raw:
            return None
        username = libcalamares.globalstorage.value('username')
        if not isinstance(username, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}\$?', username):
            raise ValueError('Target username is invalid')
        plan = json.loads(raw)
        if plan.get('kind') == 'linux':
            system = str(plan.get('system', 'Linux'))
            libcalamares.globalstorage.insert('windoesnotMigrateSystem', system[:200])
            target_root = libcalamares.globalstorage.value('rootMountPoint')
            if not isinstance(target_root, str) or not target_root.startswith('/'):
                raise ValueError('Calamares target mount point is missing')
            target_root = Path(target_root).resolve()
            if target_root == Path('/') or not (target_root / 'etc/windoesnot-image-build').is_file():
                raise ValueError('Refusing to copy outside the installation target')
            secret = libcalamares.globalstorage.value('windoesnotMigrateSecret') or ''
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8') as manifest_file:
                json.dump(plan, manifest_file); manifest_file.flush()
                script = '/usr/lib/windoesnot/mirror.py'
                with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as error_file:
                    process = subprocess.Popen([sys.executable, script, 'copy', manifest_file.name, str(target_root / 'home' / username), '--target-root', str(target_root), '--progress-json', '--secret-stdin'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=error_file, text=True)
                    process.stdin.write(secret + '\n'); process.stdin.close()
                    result = None
                    for line in process.stdout:
                        event = json.loads(line)
                        if 'errors' in event:
                            result = event
                        job = getattr(libcalamares, 'job', None)
                        if event.get('event') == 'file' and event.get('total_bytes') and hasattr(job, 'setprogress'):
                            job.setprogress(min(1.0, event['copied_bytes'] / event['total_bytes']))
                    process.wait()
                    error_file.seek(0)
                    stderr = error_file.read()
            if process.returncode or result is None:
                raise RuntimeError(stderr.strip() or 'Mirror copy failed')
            wants = target_root / 'etc/systemd/system/multi-user.target.wants'
            if wants.resolve() != wants:
                raise ValueError('Unsafe service destination')
            wants.mkdir(parents=True, exist_ok=True)
            link = wants / 'windoesnot-mirror-packages.service'
            if not link.exists() and not link.is_symlink():
                link.symlink_to('/usr/lib/systemd/system/windoesnot-mirror-packages.service')
            if result['errors']:
                warn('Linux data migration incomplete: ' + str(result['errors']))
            else:
                libcalamares.globalstorage.insert('windoesnotMigrateCompleted', True)
            return None
        system = nice_windows_name(str(((plan.get('handoff') or {}).get('windows_version')) or ''))
        libcalamares.globalstorage.insert('windoesnotMigrateSystem', system if re.fullmatch(r'[\w .()-]{1,40}', system) else '')
        handoff = plan.get('handoff') or {}
        envelope_password = libcalamares.globalstorage.value('windoesnotMigrateEnvelopeSecret') or None
        if not any(item.get('selected') for profile in plan.get('profiles', []) for item in profile.get('items', [])) and not handoff.get('wlan_selected') and not handoff.get('chromium_envelope'):
            return None
        secret = libcalamares.globalstorage.value('windoesnotMigrateSecret') or None
        target_root = libcalamares.globalstorage.value('rootMountPoint')
        if not isinstance(target_root, str) or not target_root.startswith('/'):
            raise ValueError('Calamares target mount point is missing')
        target_root = Path(target_root).resolve()
        if target_root == Path('/') or not (target_root / 'etc/windoesnot-image-build').is_file():
            raise ValueError('Refusing to copy outside the installation target')
        def progress(event):
            job = getattr(libcalamares, 'job', None)
            if event.get('event') == 'file' and event.get('total_bytes') and hasattr(job, 'setprogress'):
                job.setprogress(min(1.0, event['copied_bytes'] / event['total_bytes']))
        if envelope_password:
            # The CLI reads both secrets from stdin; neither appears in argv or the manifest.
            if any(c in envelope_password for c in '\r\n') or (secret and any(c in secret for c in '\r\n')):
                raise ValueError('Passwords must not contain line breaks')
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8') as manifest_file:
                json.dump(plan, manifest_file)
                manifest_file.flush()
                args = [sys.executable, '/usr/lib/windoesnot/migrate.py', 'copy', manifest_file.name,
                        str(target_root / 'home' / username), '--progress-json', '--nm-dir',
                        str(target_root / 'etc/NetworkManager/system-connections')]
                if secret:
                    args.append('--secret-stdin')
                args.append('--envelope-password-stdin')
                process = subprocess.run(args, input=(secret + '\n' if secret else '') + envelope_password + '\n',
                                         capture_output=True, text=True, check=False)
                if process.returncode:
                    raise RuntimeError('Browser password import failed; check the password and source')
                result = None
                for line in process.stdout.splitlines():
                    event = json.loads(line)
                    if event.get('event') == 'summary':
                        result = event
                    else:
                        progress(event)
                if result is None:
                    raise ValueError('Migration summary is missing')
        else:
            result = migrate.copy_manifest(plan, target_root / 'home' / username, secret=secret, progress=progress,
                                           nm_dir=target_root / 'etc/NetworkManager/system-connections')
        notice = (('Passwörter liegen als CSV in ~/Umzug-Windows, nach dem Browser-Import löschen.' if german
                   else 'Passwords are stored as CSV in ~/Umzug-Windows; delete them after importing into the browser.')
                  if result.get('password_csv') else '')
        if handoff.get('chromium_envelope') and not envelope_password:
            notice = ('Die Browser-Passwort-Hülle wurde ohne Passwort nicht übernommen.' if german
                      else 'The browser password envelope was not imported because no password was provided.')
        if result.get('warnings'):
            mail_notice = ('Mail-Umzug: Bitte Hinweise prüfen. ' if german else 'Mail migration: please check the notices. ') + '; '.join(w['error'] for w in result['warnings'])
            notice = (notice + '\n' if notice else '') + mail_notice
        if result['errors']:
            count = len(result['errors'])
            warn(f"Windows data migration incomplete: {count} item(s) could not be copied. First: {result['errors'][0]['path']}: {result['errors'][0]['error']}",
                 (f"{count} Element(e) konnten nicht übernommen werden; die Originale bleiben unverändert." if german
                   else f"{count} item(s) could not be copied; the originals stay untouched.")
                 + f"\n{result['errors'][0]['path']}: {result['errors'][0]['error']}" + ('\n' + notice if notice else ''))
        else:
            libcalamares.globalstorage.insert('windoesnotMigrateCompleted', True)
            if notice:
                libcalamares.globalstorage.insert('windoesnotMigrateWarning', notice)
    except Exception as error:
        warn('Windows data migration could not finish: ' + str(error),
             ('Die Daten konnten nicht übernommen werden.' if german else 'The data could not be copied.') + '\n' + str(error))
    finally:
        libcalamares.globalstorage.insert('windoesnotMigrateSecret', '')
        libcalamares.globalstorage.insert('windoesnotMigrateEnvelopeSecret', '')
    return None
