#!/usr/bin/env python3
"""Validate software profiles, offline-only operations and the Calamares handoff."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'iso/software'))
from catalog import load_catalog, read_profile, packages_for, validate_selection, pending_for, pending_reference
import install as installer
catalog=load_catalog(ROOT/'iso/software/catalog.json')
assert len([a for a in catalog['apps'] if a.get('source','offline')=='offline'])==15 and len(catalog['apps'])>15
for profile in catalog['profiles']:
 validate_selection(catalog,profile['selected'])
packages,services=packages_for(catalog,['firefox','printing','libreoffice'],'de-DE')
assert 'cups' in packages and 'libreoffice-fresh-de' in packages and services==['cups.service']
assert not packages_for(catalog,['firefox','libreoffice'],'en-US')[0].__contains__('libreoffice-fresh-de')
# Required apps come from the image, yet their language packs follow the chosen language.
assert packages_for(catalog,['firefox'],'de_DE.UTF-8')==(['firefox-i18n-de'],[])
assert packages_for(catalog,['firefox'],'en_US.UTF-8')==(['firefox-i18n-en-us'],[])
assert 'hunspell-de' in packages
assert 'hunspell-en_us' in packages_for(catalog,['firefox','libreoffice'],'en-US')[0]
# Deferred apps never reach the offline vault; they go to the wishlist with fixed references only.
sel=['firefox','google-chrome','ollama','codex-cli','gimp']
assert 'google-chrome' not in packages_for(catalog,sel,'en')[0] and 'ollama' not in packages_for(catalog,sel,'en')[0]
assert pending_for(catalog,sel)==['google-chrome','ollama','codex-cli']
by_id={a['id']:a for a in catalog['apps']}
assert pending_reference(by_id['google-chrome'])==('flatpak',['com.google.Chrome'])
assert pending_reference(by_id['ollama'])==('repo',['ollama']) and pending_reference(by_id['codex-cli'])==('aur',['openai-codex-bin'])
import copy
for mutate in [lambda a:a.update(source='npm'),lambda a:a.update(flatpak_id='not an id'),lambda a:a.update(packages=['x']),lambda a:a.pop('flatpak_id')]:
  broken=copy.deepcopy(catalog);mutate(next(a for a in broken['apps'] if a['id']=='google-chrome'))
  with tempfile.TemporaryDirectory() as tmp0:
    (Path(tmp0)/'c.json').write_text(json.dumps(broken))
    try: load_catalog(Path(tmp0)/'c.json')
    except ValueError: pass
    else: raise AssertionError('Invalid deferred application accepted')
for value in [['unknown'],['firefox','firefox'],['gimp'],'firefox']:
 try: validate_selection(catalog,value)
 except ValueError: pass
 else: raise AssertionError('Invalid selection accepted')
with tempfile.TemporaryDirectory(prefix='wdn-software-unit-') as tmp:
 d=Path(tmp);profile=d/'profile.json';profile.write_text(json.dumps({'schema_version':1,'selected':['firefox','gimp']}))
 assert read_profile(catalog,profile)==['firefox','gimp']
 profile.write_text(json.dumps({'schema_version':1,'selected':['firefox'],'command':'bad'}))
 try:read_profile(catalog,profile)
 except ValueError:pass
 else:raise AssertionError('Executable profile content accepted')
 base=d/'base';(base/'iso/software').mkdir(parents=True);shutil.copy2(ROOT/'iso/software/catalog.json',base/'iso/software/catalog.json')
 bundle=base/'offline-apps';(bundle/'repository').mkdir(parents=True)
 archive=bundle/'repository/test.pkg.tar.zst';archive.write_bytes(b'fixture')
 import hashlib
 langpack=bundle/'repository/lang.pkg.tar.zst';langpack.write_bytes(b'language fixture')
 manifest={'schema_version':1,'archives':{'test.pkg.tar.zst':{'package':'gimp','version':'1','sha256':hashlib.sha256(archive.read_bytes()).hexdigest()},'lang.pkg.tar.zst':{'package':'firefox-i18n-de','version':'1','sha256':hashlib.sha256(langpack.read_bytes()).hexdigest()}}}
 (bundle/'manifest.json').write_text(json.dumps(manifest));(bundle/'pacman.conf').write_text('[windoesnot-apps]\nServer = file:///offline\n')
 calls=[]
 def run(command,**kwargs):
  calls.append(command)
  class Result:returncode=1 if command[:2]==['pacman','-Q'] else 0
  return Result()
 record=d/'record.json'
 with patch.object(installer.subprocess,'run',side_effect=run), patch.object(installer.subprocess,'check_output',return_value='firefox-i18n-de 1\ngimp 1\n'):
  installer.install_selection(['firefox','gimp'],'de',base,record,pending=d/'pending.json')
 assert json.loads(record.read_text())['selected']==['firefox','gimp']
 assert not bundle.exists()
 assert any('-Sy' in c and '--config' in c for c in calls)
 assert any('-S' in c and 'gimp' in c for c in calls)
 assert any('-S' in c and 'firefox-i18n-de' in c for c in calls)
 assert not any('https://' in ' '.join(c) for c in calls)
 # Checksum failure must happen before any database refresh/install.
 (bundle/'repository').mkdir(parents=True);(bundle/'manifest.json').write_text(json.dumps(manifest));archive.write_bytes(b'changed');langpack.write_bytes(b'language fixture')
 calls.clear()
 with patch.object(installer.subprocess,'run',side_effect=run):
  try:installer.install_selection(['firefox','gimp'],'de',base,record,pending=d/'pending.json')
  except RuntimeError:pass
  else:raise AssertionError('Corrupt archive accepted')
 assert not any('-Sy' in c or '-S' in c for c in calls)
 assert bundle.exists()
 # An absent selection must not launch a target command.
 class Storage:
  def value(self,key):return None
 class Fake:
  globalstorage=Storage()
 with patch.dict(sys.modules,{'libcalamares':Fake()}):
  spec=importlib.util.spec_from_file_location('software_job',ROOT/'iso/modules/windoesnotapps_install/main.py');job=importlib.util.module_from_spec(spec);spec.loader.exec_module(job)
  assert isinstance(job.run(),tuple)
print('PASS: profiles, required apps, language packages, imports, offline install ordering, checksum rejection, cleanup, missing-selection protection')
