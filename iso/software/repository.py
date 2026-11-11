"""Install signed packages from the ISO snapshot, locally or over HTTPS.

Online deliberately uses the same versions as the ISO: replacing the rolling
base underneath native desktop plugins requires a separately tested rebuild.
All operations run in Calamares' disposable installation target, never the host.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlparse


def manifest_for(bundle):
    manifest = json.loads((bundle / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('archives'), dict):
        raise ValueError('Unsupported package manifest')
    for filename, data in manifest['archives'].items():
        if Path(filename).name != filename or not filename.endswith('.pkg.tar.zst'):
            raise ValueError('Invalid archive path')
        if not re.fullmatch(r'[a-zA-Z0-9@._+:-]+', data['package']):
            raise ValueError('Invalid package name')
        if not re.fullmatch(r'[0-9a-f]{64}', data['sha256']):
            raise ValueError('Invalid package checksum')
    return manifest


def download(url, destination):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only public HTTPS package URLs are supported')
    temporary = destination.with_name(destination.name + '.part')
    try:
        # CachyOS' public mirror rejects Python urllib's transport (HTTP 403)
        # while pacman/curl work. Keep HTTPS restrictions on every redirect.
        subprocess.run(['curl', '--fail', '--location', '--silent', '--show-error',
                        '--proto', '=https', '--proto-redir', '=https',
                        '--connect-timeout', '15', '--max-time', '600', '--retry', '2',
                        '--output', str(temporary), url], check=True)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def package_version(package):
    result = subprocess.run(['pacman', '-Q', package], capture_output=True, text=True)
    return result.stdout.strip().split(maxsplit=1)[1] if result.returncode == 0 else None


def install_packages(packages, mode, base):
    if mode not in ('offline', 'online'):
        raise ValueError('Unknown installation mode')
    missing = [name for name in sorted(set(packages)) if package_version(name) is None]
    if not missing:
        return
    bundle = base / 'offline-apps'
    manifest = manifest_for(bundle)
    entries = {data['package']: (filename, data) for filename, data in manifest['archives'].items()}
    if not set(missing) <= entries.keys():
        raise RuntimeError('A selected package is not available in this ISO snapshot')
    common = ['pacman', '--config', str(bundle / 'pacman.conf'), '--noconfirm']
    if mode == 'offline':
        # Check before even refreshing the isolated local repository database.
        for filename, data in manifest['archives'].items():
            if hashlib.sha256((bundle / 'repository' / filename).read_bytes()).hexdigest() != data['sha256']:
                raise RuntimeError('Offline package checksum mismatch')
    subprocess.run([*common, '-Sy'], check=True)
    plan = subprocess.check_output([*common, '-Sp', '--needed', '--print-format', '%n %v', *missing], text=True)
    required = []
    for line in plan.splitlines():
        name, version = line.split(maxsplit=1)
        existing = package_version(name)
        if existing is not None and existing != version:
            raise RuntimeError('Package installation would replace the tested ISO base: ' + name)
        if name not in entries or entries[name][1]['version'] != version:
            raise RuntimeError('Package transaction is outside the ISO snapshot: ' + name)
        required.append(name)
    if mode == 'offline':
        subprocess.run([*common, '--cachedir', str(bundle / 'repository'), '-S', '--needed', *missing], check=True)
        return
    # Never silently fall back to cached ISO archives in online mode. A network
    # failure is visible, and the user can restart the installer in offline mode.
    with tempfile.TemporaryDirectory(prefix='windoesnot-online-') as temporary:
        repository = Path(temporary)
        shutil.copyfile(bundle / 'repository/windoesnot-apps.db', repository / 'windoesnot-apps.db')
        for name in required:
            filename, data = entries[name]
            url = data.get('url', '')
            download(url, repository / filename)
            if hashlib.sha256((repository / filename).read_bytes()).hexdigest() != data['sha256']:
                raise RuntimeError('Downloaded package does not match the ISO snapshot: ' + name)
            download(url + '.sig', repository / (filename + '.sig'))
        config = repository / 'pacman.conf'
        config.write_text('[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Required\nGPGDir = /etc/pacman.d/gnupg\n[windoesnot-apps]\nServer = file://' + str(repository) + '\n')
        subprocess.run(['pacman', '--config', str(config), '--cachedir', str(repository), '--noconfirm', '-S', '--needed', *missing], check=True)

