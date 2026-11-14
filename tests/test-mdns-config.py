#!/usr/bin/env python3
"""Check mDNS ownership, installer ordering, and no-overwrite behavior."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

resolved = (ROOT / 'iso/config/resolved.conf.d/90-windoesnot-mdns.conf').read_text()
network_manager = (ROOT / 'iso/config/NetworkManager/conf.d/90-windoesnot-mdns.conf').read_text()
assert '[Resolve]' in resolved and 'MulticastDNS=no' in resolved
assert '[connection]' in network_manager and 'mdns=0' in network_manager

customize = (ROOT / 'iso/customize-image.sh').read_text()
finalize = (ROOT / 'iso/finalize-install.sh').read_text()
prepare_profile = (ROOT / 'tools/prepare-profile.py').read_text()
assert customize.index('build-image-packages.sh') < customize.index('configure-mdns.sh')
assert customize.index('build-calamares.sh') < customize.index('configure-mdns.sh')
assert finalize.index('enable "windoesnot-super-tap@$install_user.service"') < finalize.index('configure-mdns.sh')
assert "shutil.copytree(ROOT / 'iso', payload / 'iso'" in prepare_profile
assert 'avahi-daemon.service' in finalize and 'nss-mdns' in (ROOT / 'iso/packages-extra.txt').read_text()
assert 'zfs.conf' in customize and 'pacman -Qq' in customize

# Exercise the same deploy helper against a temporary root. Existing
# administrator-owned files must survive subsequent finalization unchanged.
with tempfile.TemporaryDirectory(prefix='windoesnot-mdns-') as temp:
    root = Path(temp)
    helper = ROOT / 'iso/configure-mdns.sh'
    subprocess.run(['bash', str(helper), str(root)], check=True)
    deployed_resolved = root / 'etc/systemd/resolved.conf.d/90-windoesnot-mdns.conf'
    deployed_nm = root / 'etc/NetworkManager/conf.d/90-windoesnot-mdns.conf'
    assert deployed_resolved.read_text() == resolved
    assert deployed_nm.read_text() == network_manager
    user_edit = '[Resolve]\nMulticastDNS=resolve\n'
    deployed_resolved.write_text(user_edit)
    subprocess.run(['bash', str(helper), str(root)], check=True)
    assert deployed_resolved.read_text() == user_edit
    assert deployed_nm.read_text() == network_manager

print('mDNS configuration and installation ordering: OK')
