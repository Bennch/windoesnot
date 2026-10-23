#!/usr/bin/env python3
"""Check boot option preservation, initramfs order and staging safety."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'iso'))
from boot_splash import add_hook,quiet_commandline,KERNEL_PARAMS,stage

class BootPresentation(unittest.TestCase):
    def test_systemd_and_udev_initramfs(self):
        for line in ['HOOKS=(base udev modconf kms keyboard block filesystems)\n','HOOKS=(base systemd kms keyboard sd-encrypt block filesystems)\n']:
            updated=add_hook(line)
            self.assertEqual(updated,add_hook(updated))
            self.assertLess(updated.index('kms'),updated.index('plymouth'))
            self.assertLess(updated.index('plymouth'),updated.index('windoesnot-boot-errors'))
            if 'sd-encrypt' in updated:self.assertLess(updated.index('plymouth'),updated.index('sd-encrypt'))
    def test_root_and_recovery_console_survive(self):
        result=quiet_commandline('root=UUID=test quiet loglevel=7 console=tty0 console=ttyS0,115200n8 rw rd.luks.uuid=crypt')
        self.assertEqual(result,quiet_commandline(result))
        for option in [*KERNEL_PARAMS,'root=UUID=test','rd.luks.uuid=crypt','rw']:
            self.assertIn(option,result.split())
        self.assertLess(result.index('console=ttyS0'),result.index('console=tty0'))
        self.assertNotIn('loglevel=7',result)
    def test_no_running_host_staging(self):
        with self.assertRaises(ValueError):stage('/','missing','missing')
    def test_staged_graphics_and_nonrecursive_error_handler(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            stage(root,ROOT/'iso/boot-splash',ROOT/'desktop/config/quickshell/default/img/brand/windoesnot-logo-hell.png')
            png=(root/'usr/share/plymouth/themes/windoesnot/watermark.png').read_bytes()
            import struct
            self.assertEqual(struct.unpack('>II',png[16:24]),(480,90))
            self.assertEqual((root/'usr/lib/systemd/system/windoesnot-boot-error@.service.d/99-no-recursion.conf').read_text(),'[Unit]\nOnFailure=\n')
            self.assertTrue((root/'usr/lib/windoesnot/boot-error').stat().st_mode&0o100)

if __name__=='__main__':unittest.main()
