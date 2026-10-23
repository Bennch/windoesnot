#!/usr/bin/env python3
"""Test startup ordering and failure handling without touching a display server."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class KeyboardSetup(unittest.TestCase):
 def test_setup_order_preserves_server_configuration(self):
  for result in (0,1):
   with self.subTest(result=result), tempfile.TemporaryDirectory() as temp:
    base=Path(temp); log=base/'calls'; upstream=base/'upstream'; keyboard=base/'keyboard'
    upstream.write_text('#!/bin/sh\nprintf "upstream:%s\\n" "$*" >> "'+str(log)+'"\n');upstream.chmod(0o755)
    keyboard.write_text('#!/bin/sh\nprintf "keyboard:%s\\n" "$*" >> "'+str(log)+'"\nexit '+str(result)+'\n');keyboard.chmod(0o755)
    content=(ROOT/'desktop/share/sddm/themes/windoesnot/Xsetup').read_text().replace('/usr/share/sddm/scripts/Xsetup',str(upstream)).replace('/usr/bin/setxkbmap',str(keyboard))
    script=base/'setup';script.write_text(content)
    run=subprocess.run(['sh',str(script),'test-display'],text=True,capture_output=True)
    self.assertEqual(run.returncode,0)
    self.assertEqual(log.read_text().splitlines(),['upstream:test-display','keyboard:'])
    self.assertEqual('could not initialize' in run.stderr,result!=0)
if __name__=='__main__':unittest.main()
