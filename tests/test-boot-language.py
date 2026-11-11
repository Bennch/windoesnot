#!/usr/bin/env python3
"""Focused locale, boot parameter preservation and file ownership checks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
m=load('boot_language','desktop/lib/windoesnot/boot_language.py')
p=load('boot_language_patch','tools/patch-boot-language.py')

class BootLanguage(unittest.TestCase):
    def test_effective_locale_and_unsupported_language_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'etc').mkdir();locale=root/'etc/locale.conf'
            for raw,wanted in [('LANG=de_DE.UTF-8\n','de'),('LANG=en_US.UTF-8\n','en'),
                    ('LANG=fr_FR.UTF-8\n','en'),('LANG=de_DE.UTF-8\nLC_MESSAGES=en_GB.UTF-8\n','en'),
                    ('LANG=en_US.UTF-8\nLC_ALL="de_AT.UTF-8"\n','de')]:
                locale.write_text(raw); self.assertEqual(m.language(root),wanted)

    def test_switching_all_non_grub_loaders_preserves_boot_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'etc').mkdir();(root/'var/lib/windoesnot').mkdir(parents=True)
            (root/'boot/EFI/refind').mkdir(parents=True)
            limine='/+WinDoesNot\ncomment: machine-id=123\n//linux-cachyos\nprotocol: linux\npath: boot():/vmlinuz-linux-cachyos\ncmdline: root=UUID=123 quiet\n/+Other systems and bootloaders\n//Windows Boot Manager\nprotocol: efi_chainload\npath: guid(456):/EFI/Microsoft/Boot/bootmgfw.efi\n'
            (root/'boot/limine.conf').write_text(limine)
            refind='"Boot with normal options" "rw root=UUID=123 rootflags=subvol=@"\n'
            (root/'boot/refind_linux.conf').write_text(refind)
            for loader in ['limine','refind','systemd-boot']:
                (root/'var/lib/windoesnot/installation.json').write_text(json.dumps({'schema_version':1,'bootloader':loader}))
                for lang in ['de','en','de','en']:
                    (root/'etc/locale.conf').write_text('LANG='+lang+'_DE.UTF-8\n')
                    with patch.object(m.subprocess,'run') as run:
                        self.assertEqual(m.sync(root)['language'],lang)
                        run.assert_not_called() # A locale switch never installs a loader or writes NVRAM.
            self.assertEqual((root/'boot/limine.conf').read_text(),'windoesnot_language: en\n'+limine)
            self.assertEqual((root/'boot/refind_linux.conf').read_text(),refind)
            self.assertEqual((root/'boot/loader/windoesnot-language').read_text(),'en\n')
            self.assertEqual((root/'boot/EFI/refind/windoesnot-language').read_text(),'en\n')

    def test_no_installation_and_foreign_paths_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); sentinel=root/'foreign';sentinel.mkdir();(root/'boot').symlink_to(sentinel)
            self.assertIn('skipped',m.sync(root))
            for name in ['../foreign','/boot/grub/grub.cfg','boot/loader/loader.conf']:
                with self.assertRaises(ValueError):m.owned_path(root,name)
            self.assertEqual(list(sentinel.iterdir()),[])

    def test_registered_efi_modifications_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'var/lib/windoesnot').mkdir(parents=True)
            (root/'var/lib/windoesnot/installation.json').write_text(json.dumps({'schema_version':1,'bootloader':'refind'}))
            for path in ['usr/lib/windoesnot/boot-language/refind/refind_x64.efi','usr/share/refind/refind_x64.efi']:
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'new translated loader')
            target=root/'boot/EFI/refind/refind_x64.efi';target.parent.mkdir(parents=True);target.write_bytes(b'changed externally')
            (root/m.STATE).write_text(json.dumps({'schema_version':1,'efi_files':{'boot/EFI/refind/refind_x64.efi':'previoushash'}}))
            with self.assertRaises(ValueError):m.refresh_efi(root)
            self.assertEqual(target.read_bytes(),b'changed externally')

    def test_catalogs_preserve_format_arguments_and_c_paths(self):
        for name in ['limine','refind','systemd-boot']:
            data=json.loads((ROOT/f'iso/boot-language/{name}-de.json').read_text())
            for en,de in data.items():
                with self.subTest(loader=name,text=en):self.assertEqual(p.formats(en),p.formats(de))
        self.assertEqual(p.decode(r'"\\EFI\\entries"'),r'\EFI\entries')
        self.assertEqual(p.decode(r'"\e[0m"'),'\033[0m')
        source='print("Boot in %" PRIu64 " s"); if (c == \'"\') return;'
        tokens=[t.group('group') for t in p.TOKENS.finditer(source) if t.group('group')]
        self.assertEqual(tokens,['"Boot in %" PRIu64 " s"'])

if __name__=='__main__':unittest.main()
