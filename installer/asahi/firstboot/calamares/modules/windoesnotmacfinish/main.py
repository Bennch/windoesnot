"""Finish only our installed-system setup, after Calamares created the user."""
from pathlib import Path
import pwd
import re
import subprocess
import libcalamares


def pretty_name():
    return ('WinDoesNotMac abschließen' if str(libcalamares.globalstorage.value('locale')).startswith('de')
            else 'Finish WinDoesNotMac setup')


def run():
    german = str(libcalamares.globalstorage.value('locale')).startswith('de')
    pending = Path('/var/lib/windoesnot/firstboot-pending')
    if not pending.is_file():
        return (('Einrichtungsstatus fehlt', 'Es steht keine WinDoesNotMac-Ersteinrichtung aus.') if german
                else ('Setup state missing', 'This is not a pending WinDoesNotMac first-boot setup.'))
    username = str(libcalamares.globalstorage.value('username'))
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
        return (('Ungültiges Konto', 'Im Benutzerschritt wurde kein gültiges Konto angegeben.') if german
                else ('Invalid account', 'No valid desktop account was provided by the users step.'))
    try:
        account = pwd.getpwnam(username)
        if account.pw_uid < 1000 or not Path(account.pw_dir).is_dir():
            raise ValueError('The desktop account has not been created.')
        # Initialize as the actual user: Apple defaults and installer locale choices
        # belong to this account, never to the root wizard session.
        subprocess.run(['/usr/bin/runuser', '-u', username, '--',
                        '/usr/bin/windoesnot-initialize', '--adopt-system'], check=True)
        subprocess.run(['systemctl', 'enable', 'sddm.service'], check=True)
        state = Path('/var/lib/sddm/state.conf')
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(f'[Last]\nSession=windoesnot.desktop\nUser={username}\n')
        sddm = pwd.getpwnam('sddm')
        import os
        os.chown(state, sddm.pw_uid, sddm.pw_gid)
        state.chmod(0o600)
        # The marker is the final write. Failure leaves setup pending for retry.
        pending.with_name('firstboot-complete').write_text('WinDoesNotMac setup complete\n')
        pending.unlink()
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        return ('Einrichtung konnte nicht abgeschlossen werden' if german else 'Setup could not finish', str(error))
    return None
