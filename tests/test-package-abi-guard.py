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
def run(*args,expected=0,**kwargs):
    p=subprocess.run(args,text=True,capture_output=True,timeout=45,**kwargs)
    assert p.returncode==expected,(args,p.returncode,p.stdout,p.stderr)
    return p
installed=run('pacman','-Q','hyprland').stdout.split()[1]
assert ':' not in installed,installed
upstream,release=installed.rsplit('-',1)
base=release.split('.')[0]
def simulate(name,pkgver,pkgrel,expected):
    """Offer a mock hyprland in an isolated repo/DB copy and run a print-only upgrade."""
    case=root/name;case.mkdir()
    build=case/'mock-build';build.mkdir();os.chown(build,1000,1000)
    (build/'PKGBUILD').write_text(f"pkgname=hyprland\npkgver={pkgver}\npkgrel={pkgrel}\narch=('x86_64')\npkgdesc='DEPENDENCY SIMULATION ONLY - NEVER INSTALL'\nlicense=('custom')\npackage() {{ install -d \"$pkgdir/usr/share/windoesnot-abi-test\"; echo TEST >\"$pkgdir/usr/share/windoesnot-abi-test/NEVER-INSTALL\"; }}\n")
    run('runuser','-u','vmtest','--','makepkg','--noconfirm',cwd=build)
    package=next(build.glob('*.pkg.tar.zst'))
    repo=case/'repo';repo.mkdir()
    run('repo-add',str(repo/'abi-guard.db.tar.gz'),str(package))
    db=case/'db';db.mkdir();shutil.copytree('/var/lib/pacman/local',db/'local')
    config=case/'pacman.conf'
    config.write_text(f'[options]\nArchitecture = auto\nDBPath = {db}\nSigLevel = Never\n\n[abi-guard]\nServer = file://{repo}\n')
    run('pacman','--config',str(config),'-Sy','--noconfirm')
    p=run('pacman','--config',str(config),'-Sup','--noconfirm',expected=expected)
    return p.stdout+p.stderr
# Upstream source change and a real package rebuild must both be blocked.
upstream_change=simulate('upstream-change','9999','1',1)
assert 'windoesnot-plugins' in upstream_change and 'hyprland<' in upstream_change,upstream_change
real_rebuild=simulate('real-rebuild',upstream.split(':')[-1],str(int(base)+1),1)
assert 'windoesnot-plugins' in real_rebuild and 'hyprland<' in real_rebuild,real_rebuild
# A CPU-level rebuild (cachyos-v3/v4/znver4 add .N to pkgrel) must be accepted.
cpu_rebuild=simulate('cpu-rebuild',upstream.split(':')[-1],base+'.99',0)
assert 'abi-guard' in cpu_rebuild or 'file://' in cpu_rebuild,cpu_rebuild
assert 'breaks dependency' not in cpu_rebuild,cpu_rebuild
after=run('pacman','-Q','hyprland').stdout.split()[1]
assert after==installed,(installed,after)
report={'incompatible_hyprland_update_rejected':True,'real_rebuild_rejected':True,'cpu_level_rebuild_accepted':True,'simulation_only':True,'isolated_package_database':True,'real_hyprland_unchanged':installed,'diagnostic':upstream_change,'rebuild_diagnostic':real_rebuild,'cpu_rebuild_output':cpu_rebuild}
Path('/var/tmp/abi-guard.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
