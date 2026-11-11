#!/usr/bin/env python3
"""Exercise additive menu integration using real files and isolated disk fixtures."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('boot_environment', ROOT / 'iso/boot_environment.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
ESP = '1234-ABCD'
ESP_PART = '11111111-2222-3333-4444-555555555555'
OLD = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
NEW = '01234567-89ab-cdef-0123-456789abcdef'
FIRMWARE = f'''BootCurrent: 0009
BootOrder: 0001,0002,0003,0004
Boot0001* ubuntu\tHD(1,GPT,{ESP_PART},0x800,0x10000)/\\EFI\\ubuntu\\shimx64.efi
Boot0002* Linux Boot Manager\tPciRoot(0x0)/Pci(0x1,0x0)/HD(1,GPT,{ESP_PART},0x800,0x10000)/File(\\EFI\\systemd\\systemd-bootx64.efi)
Boot0003* rEFInd Boot Manager\tHD(1,GPT,{ESP_PART},0x800,0x10000)/File(\\EFI\\refind\\refind_x64.efi)
Boot0004* Windows Boot Manager\tHD(1,GPT,{ESP_PART},0x800,0x10000)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)
Boot0009* UEFI USB\tUSB(0,0)
'''
LINES = ['/dev/test2:Ubuntu:Ubuntu:linux', '/dev/test1@/EFI/Microsoft/Boot/bootmgfw.efi:Windows Boot Manager:Windows:efi']


@contextmanager
def fixture(preferred='grub'):
    with tempfile.TemporaryDirectory(prefix='wdn-boot-test-') as directory:
        base = Path(directory); esp = base / 'esp'; old = base / 'linux'; target = base / 'target'
        for path in (esp, old, target): path.mkdir()
        files = {
            'EFI/ubuntu/shimx64.efi': 'shim fixture', 'EFI/ubuntu/grubx64.efi': 'grub fixture',
            'EFI/ubuntu/grub.cfg': f'search.fs_uuid {OLD} root\nset prefix=($root)/boot/grub\nconfigfile $prefix/grub.cfg\n',
            'EFI/systemd/systemd-bootx64.efi': 'systemd fixture', 'loader/loader.conf': 'default old-linux\ntimeout 4\n',
            'loader/entries/old-linux.conf': 'title Existing Linux\nefi /EFI/Linux/old.efi\n',
            'EFI/refind/refind_x64.efi': 'refind fixture', 'EFI/refind/refind.conf': 'timeout 12\n# personal configuration\n',
            'EFI/Microsoft/Boot/bootmgfw.efi': 'windows fixture', 'EFI/Microsoft/Boot/BCD': 'bcd fixture'}
        for relative, content in files.items():
            path = esp / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
        (old / 'etc').mkdir(); (old / 'etc/fstab').write_text(f'UUID={OLD} / ext4 defaults 0 1\nUUID={ESP} /boot/efi vfat defaults 0 2\n')
        (old / 'boot/grub').mkdir(parents=True)
        (old / 'boot/grub/grub.cfg').write_text('menuentry "Existing Linux" {}\nif [ -f ${config_directory}/custom.cfg ]; then\n source ${config_directory}/custom.cfg\nfi\n')
        (old / 'boot/grub/custom.cfg').write_text('# keep this custom entry\nmenuentry "My rescue" {}\n')
        rows = [{'path': '/dev/test1', 'fstype': 'vfat', 'uuid': ESP, 'partuuid': ESP_PART},
                {'path': '/dev/test2', 'fstype': 'ext4', 'uuid': OLD, 'partuuid': 'aaaaaaaa-1111-2222-3333-444444444444'}]
        mounts = []
        @contextmanager
        def mount(row, writable=False):
            mounts.append((row['path'], writable))
            yield esp if row['path'] == '/dev/test1' else old
        def run(args):
            if args == ['efibootmgr', '-v']:
                order={'grub':'0001,0002,0003,0004','systemd-boot':'0002,0001,0003,0004','refind':'0003,0001,0002,0004'}[preferred]
                return FIRMWARE.replace('BootOrder: 0001,0002,0003,0004','BootOrder: '+order)
            if args[0] == 'findmnt': return json.dumps({'filesystems': [{'uuid': NEW}]})
            raise AssertionError(f'Unexpected external command: {args}')
        with patch.object(boot, 'is_efi', return_value=True), patch.object(boot, 'secure_boot', return_value=False), \
             patch.object(boot, 'devices', return_value=rows), patch.object(boot, 'mounted', side_effect=mount), \
             patch.object(boot, 'command', side_effect=run), patch.object(boot, 'target_esp', return_value=(esp, ESP)):
            yield base, esp, old, target, rows, mounts


for kind in ('grub', 'systemd-boot', 'refind'):
    with fixture(kind) as (_, esp, old, target, rows, mounts):
        plans = boot.probe(LINES)['candidates']
        assert {plan['kind'] for plan in plans} == {kind}
        assert all(not writable for _, writable in mounts)
        plan = next(plan for plan in plans if plan['kind'] == kind)
        assert boot.validate_plan(plan, LINES)['id'] == plan['id']
        before = {str(path.relative_to(esp)): path.read_bytes() for path in esp.rglob('*') if path.is_file()}
        old_main = (old / 'boot/grub/grub.cfg').read_bytes()
        old_custom = (old / 'boot/grub/custom.cfg').read_text()
        new_binary = esp / 'EFI/WinDoesNot/grubx64.efi'; new_binary.parent.mkdir(); new_binary.write_text('new loader fixture')
        boot.integrate(target, plan)
        for relative, content in before.items():
            if kind == 'refind' and relative == 'EFI/refind/refind.conf': continue
            assert (esp / relative).read_bytes() == content, relative
        assert (old / 'boot/grub/grub.cfg').read_bytes() == old_main
        if kind == 'grub':
            custom = old / 'boot/grub/custom.cfg'
            assert custom.read_text().startswith(old_custom)
            assert 'chainloader ($windoesnot_esp)/EFI/WinDoesNot/grubx64.efi' in custom.read_text()
            assert custom.with_name(custom.name + '.before-windoesnot-' + NEW).read_text() == old_custom
        elif kind == 'systemd-boot':
            assert (esp / ('loader/entries/windoesnot-' + NEW + '.conf')).read_text().endswith('efi /EFI/WinDoesNot/grubx64.efi\n')
        else:
            config = esp / 'EFI/refind/refind.conf'
            assert config.read_bytes().startswith(before['EFI/refind/refind.conf'])
            assert config.with_name(config.name + '.before-windoesnot-' + NEW).read_bytes() == before['EFI/refind/refind.conf']
print('PASS: GRUB/systemd-boot/rEFInd entries added, existing menus/Windows files preserved and edited files backed up')

with tempfile.TemporaryDirectory(prefix='wdn-menu-bytes-') as directory:
    config=Path(directory)/'custom.cfg';original=b'# existing CRLF and non-UTF8 comment\r\n# \xff\r\n'
    config.write_bytes(original);config.chmod(0o600)
    boot.append_menu(config,'# new entry\n','fixture',boot.digest(config))
    backup=config.with_name('custom.cfg.before-windoesnot-fixture')
    assert backup.read_bytes()==original and config.read_bytes().startswith(original)
    assert config.stat().st_mode & 0o777 == 0o600 and backup.stat().st_mode & 0o777 == 0o600
print('PASS: existing menu bytes, line endings and private file permissions preserved in edits and backups')

with fixture() as (_, esp, old, target, rows, _):
    plan = boot.probe(LINES)['candidates'][0]
    (old / 'boot/grub/custom.cfg').write_text('changed after selection')
    try: boot.validate_plan(plan, LINES)
    except RuntimeError: pass
    else: raise AssertionError('Changed GRUB accepted')
    (esp / 'vmlinuz-linux-cachyos').write_text('existing kernel must survive')
    assert not boot.probe(LINES)['candidates']
    try: boot.guard(target)
    except RuntimeError as error: assert 'overlap' in str(error)
    else: raise AssertionError('Existing kernel collision accepted')
    assert (esp / 'vmlinuz-linux-cachyos').read_text() == 'existing kernel must survive'
    with patch.object(boot, 'devices', return_value=rows + [dict(rows[0], path='/dev/clone')]):
        assert not boot.probe(LINES)['candidates']
    with patch.object(boot, 'devices', return_value=rows + [dict(rows[0], path='/dev/clone',partuuid='ffffffff-1111-2222-3333-444444444444')]):
        assert not boot.probe(LINES)['candidates'], 'A cloned filesystem UUID is ambiguous even with different GPT identities'
    outside = old / 'outside'; outside.mkdir()
    (old / 'unsafe').symlink_to(outside)
    try: boot.safe_path(old, 'unsafe/custom.cfg')
    except RuntimeError: pass
    else: raise AssertionError('Symlink accepted')
print('PASS: changed menus, duplicate partition identities, existing kernel collisions and symlink paths rejected')

with fixture() as (_, esp, old, target, rows, _):
    with patch.object(boot, 'command', return_value=FIRMWARE.replace('BootOrder: 0001,0002,0003,0004','BootOrder: 0004,0001,0002,0003')):
        assert not boot.probe(LINES)['candidates'], 'An inactive secondary menu must not be chosen implicitly'
with fixture('refind') as (_, esp, old, target, rows, _):
    (esp / 'EFI/refind/refind.conf').write_text('scanfor internal\n')
    assert not boot.probe(LINES)['candidates'], 'Disabled manual entries must not be offered'
print('PASS: inactive secondary menus and rEFInd configurations without manual entries stay unavailable')

values={'firmwareType':'efi','locale':'de_DE.UTF-8','windoesnotBootReuse':json.dumps({'id':'fixture'}),
        'packagechooser_bootloader':'grub','windoesnotBootInstall':'none',
        'partitionChoices':{'install':'alongside'},'luksPassphrase':'synthetic-secret'}
fake=SimpleNamespace(globalstorage=SimpleNamespace(value=values.get),job=SimpleNamespace(configuration={'stage':'preflight'}),
                     utils=SimpleNamespace(warning=lambda *_:None))
with patch.dict(sys.modules,{'libcalamares':fake,'boot_environment':boot}), patch.object(boot,'validate_plan',side_effect=AssertionError('Must reject before probing or writing')):
    job_spec=importlib.util.spec_from_file_location('reuse_job',ROOT/'iso/modules/windoesnotbootreuse/main.py')
    job=importlib.util.module_from_spec(job_spec);job_spec.loader.exec_module(job)
    error=job.run();assert error and 'unverschlüsselte' in error[1] and 'synthetic-secret' not in str(error)
    values['partitionChoices']={'install':'erase'}
    error=job.run();assert error and 'Parallel dazu' in error[1]
    values['windoesnotBootReuse']=''
    assert job.run() is None
print('PASS: encrypted targets and destructive partition modes rejected before disk work; normal installation preflight remains a no-op')

with tempfile.TemporaryDirectory(prefix='wdn-config-test-') as temporary:
    config=Path(temporary);(config/'modules').mkdir()
    sequence=['windoesnotbootreuse@preflight','partition','mount','windoesnotbootreuse@guard','unpackfs','grubcfg',
              'windoesnotbootreuse@install','bootloader','windoesnotfinish','windoesnotbootreuse@finish','umount']
    settings={'sequence':[{'exec':sequence}],'instances':[]}
    for stage in ('preflight','guard','install','finish'):
        name='windoesnotbootreuse-'+stage+'.conf'
        settings['instances'].append({'module':'windoesnotbootreuse','id':stage,'config':name})
        (config/'modules'/name).write_text(json.dumps({'stage':stage}))
    (config/'settings.conf').write_text(json.dumps(settings))
    (config/'modules/bootloader.conf').write_text(json.dumps({'efiBootLoaderVar':'windoesnotBootInstall'}))
    assert boot.configuration_ready(config)
    sequence.remove('windoesnotbootreuse@guard')
    (config/'settings.conf').write_text(json.dumps(settings))
    assert not boot.configuration_ready(config),'An older sequence without the pre-copy guard must not offer reuse'
print('PASS: complete installer workflow accepted; stale configuration without its safety jobs refused')

with tempfile.TemporaryDirectory(prefix='wdn-mount-test-') as temporary:
    mountpoint = Path(temporary) / 'mount'; mountpoint.mkdir(); calls = []
    def failing_unmount(args):
        calls.append(args)
        if args[0] == 'umount': raise RuntimeError('intentional unmount failure')
        return ''
    with patch.object(boot.tempfile, 'mkdtemp', return_value=str(mountpoint)), patch.object(boot, 'command', side_effect=failing_unmount):
        try:
            with boot.mounted({'path': '/dev/test2', 'fstype': 'ext4'}) as directory:
                (directory / 'must-survive').write_text('data')
        except RuntimeError: pass
        else: raise AssertionError('Unmount failure hidden')
    assert (mountpoint / 'must-survive').read_text() == 'data'
    assert 'ro,noload,nosuid,nodev,noexec' in calls[0]
print('PASS: inspection uses read-only/no-replay mounts; failed unmount never recursively deletes contents')
