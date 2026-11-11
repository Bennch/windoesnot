# SPDX-License-Identifier: GPL-3.0-or-later
"""Detect CPU level and graphics, enable optimized packages, drivers and mirrors.

Every finding is shown as the job's status line so the user can follow what
was recognized. The same summary is stored in the target for the first login.
"""
import json
from pathlib import Path
import time
import libcalamares

STATUS = ''
SCRIPT = '/usr/share/windoesnot/iso/system_setup.py'
PROFILES = {
    'nvidia-open-dkms': ('NVIDIA', 'NVIDIA'),
    'nvidia-open-dkms.prime': ('NVIDIA mit Hybridgrafik (Laptop)', 'NVIDIA hybrid graphics (laptop)'),
    'nouveau': ('NVIDIA (nouveau)', 'NVIDIA (nouveau)'),
    'intel': ('Intel', 'Intel'),
    'amd': ('AMD', 'AMD'),
    'qemu': ('virtuelle Maschine (QEMU/KVM)', 'virtual machine (QEMU/KVM)'),
    'virtualbox': ('virtuelle Maschine (VirtualBox)', 'virtual machine (VirtualBox)'),
    'vmware': ('virtuelle Maschine (VMware)', 'virtual machine (VMware)'),
    'fallback': ('Standardgrafik', 'standard graphics'),
}
LEVELS = {'znver4': 'AMD Zen 4/5', 'v4': 'x86-64-v4', 'v3': 'x86-64-v3'}


def german():
    return str(libcalamares.globalstorage.value('locale')).startswith('de')


def text(de, en):
    return de if german() else en


def pretty_name():
    return text('System für deinen Rechner einrichten', 'Set up the system for your computer')


def pretty_status_message():
    return STATUS or pretty_name()


def show(progress, de, en, pause=0.0):
    global STATUS
    STATUS = text(de, en)
    libcalamares.utils.debug('windoesnotsystem: ' + STATUS)
    libcalamares.job.setprogress(progress)
    # Long enough to read; the whole job stays well under a minute offline.
    time.sleep(pause)


def record(root):
    path = root / 'var/lib/windoesnot/system-setup.json'
    return json.loads(path.read_text()) if path.is_file() else {}


def stage(name, mode):
    command = ['/usr/bin/env', 'WINDOESNOT_INSTALL_TARGET=1', '/usr/bin/python3', SCRIPT, name, '--mode', mode]
    return libcalamares.utils.target_env_call(command)


def run():
    mode = libcalamares.job.configuration.get('mode')
    value = libcalamares.globalstorage.value('rootMountPoint')
    if mode not in ('online', 'offline') or not isinstance(value, str) or not value:
        return ('Invalid installation target', 'The installation mode or root mount point is missing.')
    root = Path(value).resolve()
    if root == Path('/') or not (root / 'etc/windoesnot-image-build').is_file():
        return ('Invalid installation target', 'Refusing to modify the live root.')

    show(0.05, 'Prozessor wird erkannt …', 'Detecting the processor …')
    if stage('pacman', mode):
        return (text('Paketquellen konnten nicht eingerichtet werden', 'Package sources could not be configured'), 'See the installation log for details.')
    level = record(root).get('cpu_level')
    if level in LEVELS:
        show(0.2, f'Prozessor unterstützt {LEVELS[level]}: optimierte CachyOS-Pakete eingeschaltet',
             f'Processor supports {LEVELS[level]}: optimized CachyOS packages enabled', 2.5)
    else:
        show(0.2, 'Prozessor erkannt: Standardpakete (x86-64) werden verwendet',
             'Processor detected: using standard x86-64 packages', 2.5)

    show(0.3, 'Grafikkarte wird erkannt und Treiber werden eingerichtet …', 'Detecting graphics and setting up drivers …')
    # A driver problem must not abort the installation: mesa/fallback stays usable.
    if stage('drivers', mode):
        libcalamares.utils.warning('windoesnotsystem: driver setup failed, see log')
    data = record(root)
    names = [PROFILES.get(p, (p, p))[0 if german() else 1] for p in data.get('driver_profiles', [])]
    if data.get('drivers') == 'configured' and names:
        show(0.7, 'Treiber eingerichtet: ' + ', '.join(names), 'Drivers set up: ' + ', '.join(names), 2.5)
    else:
        show(0.7, 'Für deine Grafikkarte wird der Treiber nach dem ersten Update eingerichtet',
             'The graphics driver will be set up after the first update', 2.5)

    if mode == 'online':
        show(0.75, 'Schnellste Download-Server werden ermittelt …', 'Finding the fastest download servers …')
        stage('mirrors', mode)
        if record(root).get('mirrors_ranked'):
            show(1.0, 'Schnellste Download-Server ausgewählt', 'Fastest download servers selected', 1.5)
        else:
            show(1.0, 'Download-Server werden beim nächsten Start ermittelt', 'Download servers will be ranked on the next start', 1.5)
    else:
        show(1.0, 'Download-Server werden bei der ersten Internetverbindung ermittelt',
             'Download servers will be ranked on the first internet connection', 1.5)
    return None
