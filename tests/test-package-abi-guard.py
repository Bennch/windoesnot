"""VM-only dependency simulation; the mock Hyprland package is NEVER installed."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

assert subprocess.run(['systemd-detect-virt','--vm','--quiet']).returncode==0
assert Path('/usr/share/windoesnot/IMAGE-PACKAGES.txt').is_file()
root=Path(tempfile.mkdtemp(prefix='windoesnot-abi-guard-',dir='/var/tmp'))
root.chmod(0o755)
build=root/'mock-build';build.mkdir();os.chown(build,1000,1000)
(build/'PKGBUILD').write_text("pkgname=hyprland\npkgver=9999\npkgrel=1\narch=('x86_64')\npkgdesc='DEPENDENCY SIMULATION ONLY - NEVER INSTALL'\nlicense=('custom')\npackage() { install -d \"$pkgdir/usr/share/windoesnot-abi-test\"; echo TEST >\"$pkgdir/usr/share/windoesnot-abi-test/NEVER-INSTALL\"; }\n")
def run(*args,expected=0,**kwargs):
    p=subprocess.run(args,text=True,capture_output=True,timeout=45,**kwargs)
    assert p.returncode==expected,(args,p.returncode,p.stdout,p.stderr)
    return p
run('runuser','-u','vmtest','--','makepkg','--noconfirm',cwd=build)
package=next(build.glob('*.pkg.tar.zst'))
repo=root/'repo';repo.mkdir()
run('repo-add',str(repo/'abi-guard.db.tar.gz'),str(package))
db=root/'db';db.mkdir();shutil.copytree('/var/lib/pacman/local',db/'local')
config=root/'pacman.conf'
config.write_text(f'[options]\nArchitecture = auto\nDBPath = {db}\nSigLevel = Never\n\n[abi-guard]\nServer = file://{repo}\n')
run('pacman','--config',str(config),'-Sy','--noconfirm')
p=run('pacman','--config',str(config),'-Sup','--noconfirm',expected=1)
text=p.stdout+p.stderr
assert 'windoesnot-plugins' in text and 'hyprland=' in text,text
installed=run('pacman','-Q','hyprland').stdout.strip()
assert '9999' not in installed
report={'incompatible_hyprland_update_rejected':True,'simulation_only':True,'isolated_package_database':True,'real_hyprland_unchanged':installed,'diagnostic':text}
Path('/var/tmp/abi-guard.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
