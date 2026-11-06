#!/usr/bin/env python3
"""Flathub is preconfigured system-wide and its catalogue refresh is wired into the image."""
import base64
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
repo = (ROOT / 'iso/flatpak/flathub.flatpakrepo').read_text()
assert repo.startswith('[Flatpak Repo]') and 'Url=https://dl.flathub.org/repo/' in repo
key = re.search(r'^GPGKey=(\S+)$', repo, re.M).group(1)
assert base64.b64decode(key)[:1] in (b'\x99', b'\x98'), 'not an OpenPGP public key block'
service = (ROOT / 'iso/flatpak/windoesnot-flathub-appstream.service').read_text()
timer = (ROOT / 'iso/flatpak/windoesnot-flathub-appstream.timer').read_text()
assert 'flatpak update --appstream --noninteractive' in service and 'ConditionPathExists=/etc/flatpak/remotes.d/flathub.flatpakrepo' in service
assert 'OnBootSec=' in timer and 'WantedBy=timers.target' in timer
profile = (ROOT / 'tools/prepare-profile.py').read_text()
assert "etc/flatpak/remotes.d/flathub.flatpakrepo" in profile and "'windoesnot-flathub-appstream.timer'" in profile
assert 'systemctl enable windoesnot-flathub-appstream.timer' in (ROOT / 'iso/customize-image.sh').read_text()
packages = (ROOT / 'iso/packages-extra.txt').read_text().split()
assert 'flatpak' in packages and 'papirus-icon-theme' in packages
print('PASS flatpak-remote')
