"""Disposable VM integration test: corrupt signature rejection, then real upgrade."""
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

assert subprocess.run(['systemd-detect-virt','--vm','--quiet']).returncode==0
assert Path('/usr/share/windoesnot/IMAGE-PACKAGES.txt').is_file()
repo=Path('/var/tmp/windoesnot-signed-repo');repo.mkdir(exist_ok=True)
with tarfile.open('/tmp/repo-test-metadata.tar.gz') as archive: archive.extractall(repo,filter='data')
for package in Path('/home/vmtest/package-build-4').glob('*.pkg.tar.zst'):shutil.copy2(package,repo/package.name)
metadata=json.loads((repo/'REPOSITORY.json').read_text())
assert metadata['signed'] and metadata['private_test_only']
keyring=Path('/var/tmp/windoesnot-test-keyring');keyring.mkdir(mode=0o700,exist_ok=True)
def call(*args,expected=0):
    p=subprocess.run(args,text=True,capture_output=True,timeout=90)
    assert p.returncode==expected,(args,p.returncode,p.stdout,p.stderr)
    return p.stdout+p.stderr
call('pacman-key','--gpgdir',str(keyring),'--init')
call('pacman-key','--gpgdir',str(keyring),'--add',str(repo/'TEST-KEY.asc'))
call('pacman-key','--gpgdir',str(keyring),'--lsign-key',metadata['key'])
config=Path('/var/tmp/windoesnot-repo-test.conf')
cache=Path('/var/tmp/windoesnot-test-cache');cache.mkdir(exist_ok=True)
config.write_text(f'[options]\nArchitecture = auto\nGPGDir = {keyring}\nCacheDir = {cache}\nSigLevel = Required DatabaseRequired\nLocalFileSigLevel = Required\n\n[windoesnot]\nServer = file://{repo}\n')
sig=repo/'windoesnot.db.sig';original=sig.read_bytes()
sig.write_bytes(b'INVALID TEST SIGNATURE\n')
rejection=call('pacman','--config',str(config),'-Syy','--noconfirm',expected=1)
assert 'signature' in rejection.lower(),rejection
sig.write_bytes(original)
upgrade=call('pacman','--config',str(config),'-Syyu','--noconfirm')
installed=subprocess.check_output(['pacman','-Q',*sorted(metadata['packages'])],text=True,stderr=subprocess.DEVNULL)
versions={line.split()[0]:line.split()[1] for line in installed.splitlines()}
assert all(version=='0.1.0-4' for version in versions.values()),versions
report={'corrupt_database_signature_rejected':True,'required_package_and_database_signatures':True,'test_key_only':metadata['key'],'versions_after_signed_repository_upgrade':versions}
Path('/var/tmp/signed-upgrade.json').write_text(json.dumps(report,indent=2)+'\n')
Path('/var/tmp/signed-upgrade.log').write_text('REJECTED INVALID SIGNATURE:\n'+rejection+'\nVALID SIGNED UPGRADE:\n'+upgrade)
print(json.dumps(report,indent=2))
