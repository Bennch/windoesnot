#!/usr/bin/env python3
"""Stage pinned bootloader sources and exact local patches for an offline build."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def prepare(output, cache, offline=False):
    if output.exists():
        raise ValueError('Use a new output directory')
    pins = json.loads((ROOT / 'iso/boot-language/sources.json').read_text())
    cache.mkdir(parents=True, exist_ok=True)
    archives = []
    for pin in pins['archives']:
        archive = cache / pin['file']
        if not archive.exists():
            if offline:
                raise ValueError('Pinned source is missing from cache: ' + pin['file'])
            temporary = archive.with_suffix(archive.suffix + '.download')
            try:
                with urllib.request.urlopen(pin['url'], timeout=60) as response, temporary.open('wb') as stream:
                    shutil.copyfileobj(response, stream)
                if hashlib.sha256(temporary.read_bytes()).hexdigest() != pin['sha256']:
                    raise ValueError('Upstream source checksum mismatch: ' + pin['file'])
                temporary.replace(archive)
            finally:
                temporary.unlink(missing_ok=True)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('Cached source checksum mismatch: ' + pin['file'])
        archives.append(archive)
    # Explicit allowlist: no desktop preferences, build state or credentials.
    files = [ROOT / 'tools/patch-boot-language.py', ROOT / 'tools/build-boot-language-source.sh',
             ROOT / 'desktop/lib/windoesnot/boot_language.py',
             *sorted((ROOT / 'iso/boot-language').glob('*.json')), *sorted((ROOT / 'iso/boot-language').glob('*.patch')), ROOT / 'iso/boot-language/README.md',
             *sorted((ROOT / 'desktop/share/systemd/system').glob('windoesnot-boot-language.*')),
             *sorted((ROOT / 'desktop/share/libalpm/hooks').glob('*boot-language.hook'))]
    output.mkdir(parents=True)
    bundle = output / 'windoesnot-boot-language-source.tar.gz'
    with bundle.open('wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w|') as stream:
        for path, relative in [(p, str(p.relative_to(ROOT))) for p in files] + [(p, 'archives/' + p.name) for p in archives]:
            info = stream.gettarinfo(str(path), 'windoesnot-boot-language/' + relative)
            info.uid = info.gid = 0; info.uname = info.gname = ''; info.mtime = 0
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            with path.open('rb') as source:
                stream.addfile(info, source)
    checksum = hashlib.sha256(bundle.read_bytes()).hexdigest()
    template = (ROOT / 'packaging/boot-language/PKGBUILD.in').read_text()
    (output / 'PKGBUILD').write_text(template.replace('@SHA256@', checksum))
    return {'source_sha256': checksum, 'archives': pins['archives']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=ROOT / 'build/boot-language-sources')
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.cache, args.offline), indent=2))

if __name__ == '__main__':
    main()
