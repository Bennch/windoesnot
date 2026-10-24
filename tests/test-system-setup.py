#!/usr/bin/env python3
"""Host-safe checks for CPU-level repositories, chwd snapshot packages and the setup notice."""
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'iso'), str(ROOT / 'iso/software')]
import system_setup as setup
import prepare

IMAGE_CONF = '''[options]
HoldPkg     = pacman glibc
Architecture = auto
ParallelDownloads = 10
DisableSandbox
SigLevel    = Required DatabaseOptional

[cachyos]
Server = https://mirror.cachyos.org/repo/$arch/$repo

[core]
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch

[extra]
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch

[multilib]
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch
'''

# CPU levels exactly as glibc reports them; unsupported levels have no parenthesis.
V3 = '  x86-64-v4\n  x86-64-v3 (supported, searched)\n  x86-64-v2 (supported, searched)\n'
V4 = '  x86-64-v4 (supported, searched)\n  x86-64-v3 (supported, searched)\n'
GENERIC = '  x86-64-v4\n  x86-64-v3\n  x86-64-v2 (supported, searched)\n'
ZEN4 = 'vendor_id\t: AuthenticAMD\ncpu family\t: 25\nmodel\t\t: 97\nflags\t\t: fpu sse avx2 avx512f\n'
ZEN3 = 'vendor_id\t: AuthenticAMD\ncpu family\t: 25\nmodel\t\t: 33\nflags\t\t: fpu sse avx2\n'
ZEN5 = 'vendor_id\t: AuthenticAMD\ncpu family\t: 26\nmodel\t\t: 68\nflags\t\t: fpu avx512f\n'
INTEL = 'vendor_id\t: GenuineIntel\ncpu family\t: 6\nmodel\t\t: 143\nflags\t\t: fpu avx512f\n'
assert setup.cpu_level(V4, ZEN4) == 'znver4'
assert setup.cpu_level(V4, ZEN5) == 'znver4'
assert setup.cpu_level(V3, ZEN3) == 'v3'
assert setup.cpu_level(V4, INTEL) == 'v4'
assert setup.cpu_level(GENERIC, '') is None

conf = setup.configure_pacman(IMAGE_CONF, 'v3')
sections = [line for line in conf.splitlines() if line.startswith('[')]
assert sections == ['[options]', '[cachyos-v3]', '[cachyos-core-v3]', '[cachyos-extra-v3]', '[cachyos]', '[core]', '[extra]', '[multilib]'], sections
assert 'Server =' not in conf and 'DisableSandbox' not in conf and 'DownloadUser = alpm' in conf
assert 'Include = /etc/pacman.d/cachyos-v3-mirrorlist' in conf and 'Include = /etc/pacman.d/mirrorlist' in conf
assert setup.configure_pacman(conf, 'v3') == conf, 'not idempotent'
assert '-v3' not in setup.configure_pacman(conf, None)
assert 'cachyos-extra-znver4' in setup.configure_pacman(conf, 'znver4')
assert setup.configure_pacman(IMAGE_CONF, 'v4').count('cachyos-v4-mirrorlist') == 3

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    profiles = root / 'profiles.toml'
    profiles.write_text('''
[nvidia-open-dkms]
packages = 'nvidia-utils lib32-nvidia-utils'
conditional_packages = """
    for pkgbase in /usr/lib/modules/*/pkgbase; do modules+=" ${kernel}-nvidia-open"; done
    [ -z "$modules" ] && modules="nvidia-open-dkms"
    echo "$modules"
"""
[nvidia-open-dkms.prime]
packages = 'nvidia-utils nvidia-prime'
[nvidia-dkms-580xx]
packages = 'nvidia-580xx-dkms nvidia-580xx-utils'
[intel]
packages = 'mesa vulkan-intel'
conditional_packages = """
if [ -z "$(lspci -d "10de:*:030x")" ]; then
    echo "opencl-mesa lib32-opencl-mesa"
fi
"""
''')
    modules = root / 'modules'
    for version, base in [('7.2.7-1-cachyos', 'linux-cachyos'), ('6.18.50-1-cachyos-lts', 'linux-cachyos-lts')]:
        (modules / version).mkdir(parents=True)
        (modules / version / 'pkgbase').write_text(base + '\n')
    packages = prepare.chwd_packages(profiles, modules)
    assert packages == sorted(['nvidia-utils', 'lib32-nvidia-utils', 'nvidia-prime', 'mesa', 'vulkan-intel', 'opencl-mesa',
                               'lib32-opencl-mesa', 'linux-cachyos-nvidia-open', 'linux-cachyos-lts-nvidia-open']), packages
    assert not any('580xx' in name or name.endswith('-dkms') for name in packages)

    bundle = root / 'bundle'; (bundle / 'repository').mkdir(parents=True)
    work = root / 'work'; work.mkdir()
    config = setup.driver_config(bundle, work)
    text = config.read_text()
    # chwd strips lib32 packages unless a line starts with [multilib]. No own DBPath:
    # pacman replaced a symlinked local/ and dropped the new entries (r11).
    assert '\n[multilib]\n' in text and 'DBPath' not in text
    assert (work / 'server/multilib.db').readlink() == bundle / 'repository/windoesnot-apps.db'

    sync = root / 'sync'; sync.mkdir()
    (sync / 'multilib.db').write_text('real')
    with setup.snapshot_multilib(sync):
        assert not (sync / 'multilib.db').exists()
        (sync / 'multilib.db').write_text('snapshot')
    assert (sync / 'multilib.db').read_text() == 'real' and not list(sync.glob('*.windoesnot-saved'))
    with setup.snapshot_multilib(sync):
        (sync / 'multilib.db').write_text('snapshot')
    (sync / 'multilib.db').unlink()
    with setup.snapshot_multilib(sync):
        (sync / 'multilib.db').write_text('snapshot')
    assert not (sync / 'multilib.db').exists()

    local = root / 'local'
    (local / 'complete-1-1').mkdir(parents=True); (local / 'complete-1-1/desc').write_text('x')
    (local / 'lib32-glibc-2-1').mkdir()
    (local / 'ALPM_DB_VERSION').write_text('9')
    assert setup.incomplete_entries(local) == ['lib32-glibc-2-1']

    record = root / 'target'
    setup.update_record(record, cpu_level='v3', driver_reason='earlier failure')
    setup.update_record(record, drivers='configured', driver_profiles=['intel', 'nvidia-open-dkms.prime'], driver_reason=None)
    data = json.loads((record / setup.RECORD).read_text())
    assert data == {'schema_version': 1, 'cpu_level': 'v3', 'drivers': 'configured', 'driver_profiles': ['intel', 'nvidia-open-dkms.prime']}

loader = importlib.machinery.SourceFileLoader('notice', str(ROOT / 'desktop/bin/windoesnot-setup-notice'))
spec = importlib.util.spec_from_loader('notice', loader)
notice = importlib.util.module_from_spec(spec); loader.exec_module(notice)
lines = notice.summary({'cpu_level': 'v3', 'drivers': 'configured', 'driver_profiles': ['intel', 'nvidia-open-dkms.prime'], 'mirrors_ranked': False}, True)
assert lines == ['Optimierte Pakete für x86-64-v3', 'Treiber: Intel, NVIDIA mit Hybridgrafik', 'Download-Server werden bei der ersten Internetverbindung gewählt'], lines
assert notice.summary({'cpu_level': 'x86-64', 'drivers': 'pending'}, False)[:2] == ['Standard packages (x86-64)', 'Graphics driver follows with the first update']

dispatcher = ROOT / 'desktop/share/NetworkManager/dispatcher.d/90-windoesnot-first-network'
assert dispatcher.stat().st_mode & 0o777 == 0o755
subprocess.run(['sh', '-n', str(dispatcher)], check=True)
unit = (ROOT / 'desktop/share/systemd/system/windoesnot-first-network.service').read_text()
assert 'ConditionPathExists=!/var/lib/windoesnot/mirrors-ranked' in unit and '[Install]' not in unit
print('PASS: CPU levels, pacman.conf rewrite, chwd snapshot packages, isolated driver config, setup notice, first-network trigger')
