#!/usr/bin/env python3
"""Build an offline-only app repository inside the image, never on the host."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from catalog import load_catalog
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from installation import BOOT_EXTRA_PACKAGES

BASE = Path('/usr/share/windoesnot')
BUNDLE = BASE / 'offline-apps'
CHWD_PROFILES = Path('/var/lib/chwd/db/pci/graphic_drivers/profiles.toml')


def chwd_packages(profiles=CHWD_PROFILES, modules=Path('/usr/lib/modules')):
    """Every package a graphics profile may request, except profiles that build DKMS modules.

    chwd resolves its targets against the snapshot repository only, so already
    installed packages (mesa, nvidia-utils, kernel modules) must be in it too.
    """
    kernels = sorted(path.read_text().strip() for path in modules.glob('*/pkgbase'))
    def walk(table):
        yield table
        for value in table.values():
            if isinstance(value, dict):
                yield from walk(value)
    names = set()
    for top in tomllib.loads(profiles.read_text()).values():
        for profile in walk(top):
            packages = profile.get('packages', '').split()
            if not packages or any(name.endswith('-dkms') for name in packages):
                continue
            names.update(packages)
            script = profile.get('conditional_packages', '')
            # Literal alternatives only; computed module names are added per kernel.
            for words in re.findall(r'echo "([^"$]*)"', script):
                names.update(words.split())
            if '-nvidia-open' in script:
                names.update(kernel + '-nvidia-open' for kernel in kernels if kernel.startswith('linux-cachyos'))
    return sorted(names)


@contextmanager
def build_resolver(staged=Path('/root/.windoesnot-build-resolv.conf'), resolver=Path('/etc/resolv.conf')):
    # arch-chroot -N mounts the image root after its resolver bind, hiding that
    # bind. Use a build-only copy and restore the clean image file even on error.
    content = staged.read_bytes() if staged.is_file() else None
    staged.unlink(missing_ok=True)
    original = None
    if content is not None and not os.path.ismount(resolver):
        original = resolver.read_bytes()
        resolver.write_bytes(content)
    try:
        yield
    finally:
        if original is not None:
            resolver.write_bytes(original)


def main():
    if os.geteuid() != 0 or not Path('/etc/windoesnot-image-build').is_file():
        raise SystemExit('Image build only')
    catalog_path = BASE / 'iso/software/catalog.json'
    catalog = load_catalog(catalog_path)
    repository = BUNDLE / 'repository'; repository.mkdir(parents=True, exist_ok=True)
    packages = set(BOOT_EXTRA_PACKAGES)
    for app in catalog['apps']:
        if not app.get('required'):
            packages.update(app['packages'])
        for names in app.get('localizations', {}).values():
            packages.update(names)
    # Isolated trust database: build roots do not run the live keyring service.
    with tempfile.TemporaryDirectory(prefix='windoesnot-app-signatures-') as temporary:
        keyring = Path(temporary) / 'gnupg'; keyring.mkdir(mode=0o700)
        subprocess.run(['pacman-key', '--gpgdir', str(keyring), '--init'], check=True)
        subprocess.run(['pacman-key', '--gpgdir', str(keyring), '--populate', 'archlinux', 'cachyos'], check=True)
        drivers = chwd_packages()
        with build_resolver():
            plan = subprocess.check_output(['pacman', '-Sp', '--needed', '--noconfirm', '--gpgdir', str(keyring), '--print-format', '%n %l', *sorted(packages)], text=True)
            urls = dict(line.split(maxsplit=1) for line in plan.splitlines())
            subprocess.run(['pacman', '-Sw', '--needed', '--noconfirm', '--cachedir', str(repository), '--gpgdir', str(keyring), *sorted(packages)], check=True)
            # Without --needed: installed driver packages are chwd targets as well.
            plan = subprocess.check_output(['pacman', '-Sp', '--noconfirm', '--gpgdir', str(keyring), '--print-format', '%n %l', *drivers], text=True)
            urls.update(line.split(maxsplit=1) for line in plan.splitlines())
            subprocess.run(['pacman', '-Sw', '--noconfirm', '--cachedir', str(repository), '--gpgdir', str(keyring), *drivers], check=True)
        archives = sorted(repository.glob('*.pkg.tar.zst'))
        manifest = {'schema_version': 1, 'archives': {}, 'requested_packages': sorted(packages), 'chwd_packages': drivers}
        metadata = {}
        for archive in archives:
            # Verify the actual detached signatures before putting files on the ISO.
            if not archive.with_name(archive.name + '.sig').is_file():
                raise RuntimeError('Missing package signature: ' + archive.name)
            subprocess.run(['pacman-key', '--gpgdir', str(keyring), '--verify', str(archive) + '.sig', str(archive)], check=True)
            name, version = subprocess.check_output(['pacman', '-Qp', str(archive)], text=True).split()
            metadata[name] = archive
            manifest['archives'][archive.name] = {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'package': name, 'version': version, 'url': urls[name]}
        if archives:
            subprocess.run(['repo-add', str(repository / 'windoesnot-apps.db.tar.gz'), *map(str, archives)], check=True)
        # chwd runs pacman --needed: a package already in the image at this
        # version needs its database entry only, never a second archive copy.
        installed = dict(line.split() for line in subprocess.check_output(['pacman', '-Q'], text=True).splitlines())
        manifest['database_only'] = []
        for filename, data in list(manifest['archives'].items()):
            if installed.get(data['package']) == data['version']:
                if data['package'] not in drivers:
                    raise RuntimeError('Installed package in app snapshot: ' + data['package'])
                del manifest['archives'][filename]
                metadata.pop(data['package'], None)
                (repository / filename).unlink()
                (repository / (filename + '.sig')).unlink()
                manifest['database_only'].append(data['package'])
    # Pull the application icon from the very same signed package archives.
    icons = catalog_path.parent / 'icons'; icons.mkdir(exist_ok=True)
    for app in catalog['apps']:
        archive = metadata.get(app['packages'][0])
        if archive is None:
            continue
        process = subprocess.Popen(['zstd', '-dc', str(archive)], stdout=subprocess.PIPE)
        candidates = []
        with tarfile.open(fileobj=process.stdout, mode='r|') as stream:
            for entry in stream:
                path = Path(entry.name)
                if entry.isfile() and (entry.name.startswith('usr/share/icons/hicolor/') or entry.name.startswith('usr/share/pixmaps/')) and path.suffix.lower() in ('.svg', '.png', '.xpm'):
                    key = path.stem.lower()
                    terms = [app['id'], app['packages'][0], 'libreoffice-startcenter' if app['id'] == 'libreoffice' else '']
                    if any(term and (key == term or key.endswith('.' + term) or term in key) for term in terms):
                        if entry.size < 2 * 1024 * 1024:
                            candidates.append((0 if path.suffix == '.svg' and 'scalable' in path.parts else 1, entry.size, path.suffix, stream.extractfile(entry).read()))
        process.stdout.close()
        if process.wait(): raise RuntimeError('Cannot read icon package')
        if candidates:
            candidates.sort(key=lambda x: (x[0], -x[1]))
            chosen = candidates[0]; (icons / (app['id'] + chosen[2])).write_bytes(chosen[3])
    manifest['base_packages'] = subprocess.check_output(['pacman', '-Q'], text=True).splitlines()
    (BUNDLE / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    # Only this version-matched repository is consulted by the installer.
    (BUNDLE / 'pacman.conf').write_text('[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Required\nGPGDir = /etc/pacman.d/gnupg\n[windoesnot-apps]\nServer = file:///usr/share/windoesnot/offline-apps/repository\n')
    print('Offline app repository ready:', len(archives), 'signed packages')


if __name__ == '__main__':
    main()
