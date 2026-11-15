#!/usr/bin/env python3
"""Create the standalone install-dotfiles.sh for the download page.

The script inside the dotfiles archive finds its sources next to itself. The published copy additionally knows the
URL and SHA-256 of the matching archive, downloads and verifies it, and then continues from there. Only those two
variables differ; everything else is byte-identical to tools/install-dotfiles.sh.
"""
import argparse
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', required=True, help='HTTPS URL of windoesnot-dotfiles-<version>.tar.gz')
parser.add_argument('--sha256', required=True, help='SHA-256 of that archive')
parser.add_argument('--output', required=True, type=Path, help='directory for install-dotfiles.sh and its checksum files')
args = parser.parse_args()
if not re.fullmatch(r'https://download\.windoesnot\.me/[0-9][0-9.-]*/windoesnot-dotfiles-[0-9][0-9.-]*\.tar\.gz', args.url):
    parser.error('--url must be the dotfiles archive under download.windoesnot.me')
if not re.fullmatch(r'[0-9a-f]{64}', args.sha256):
    parser.error('--sha256 must be 64 lowercase hex digits')
source = (ROOT / 'tools/install-dotfiles.sh').read_text(encoding='utf-8')
for name, value in (('WDN_DOTFILES_URL', args.url), ('WDN_DOTFILES_SHA256', args.sha256)):
    source, count = re.subn(rf"^{name}=''$", f"{name}='{value}'", source, count=1, flags=re.M)
    if count != 1:
        raise SystemExit(f'{name} placeholder not found in tools/install-dotfiles.sh')
args.output.mkdir(parents=True, exist_ok=True)
target = args.output / 'install-dotfiles.sh'
target.write_text(source, encoding='utf-8')
target.chmod(0o755)
data = target.read_bytes()
(args.output / 'install-dotfiles.sh.sha256').write_text(f'{hashlib.sha256(data).hexdigest()}  install-dotfiles.sh\n')
(args.output / 'install-dotfiles.sh.md5').write_text(f'{hashlib.md5(data).hexdigest()}  install-dotfiles.sh\n')
print(target, len(data), 'bytes')
