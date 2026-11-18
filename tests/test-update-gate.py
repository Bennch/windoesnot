#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from update_gate_common import REQUIRED, package_set, validate

class Gate(unittest.TestCase):
    def test_fresh_complete_only_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); pkgs = base / 'pkgs'; pkgs.mkdir()
            pkg = pkgs / 'test-1-x86_64.pkg.tar.zst'; pkg.write_bytes(b'one')
            digest = package_set(pkgs)
            result = {'timestamp': datetime.now(timezone.utc).isoformat(), 'package_set_sha256': digest,
                      'exit_code': 0, 'checks': {k: True for k in REQUIRED}}
            result_path = base / (digest + '.json')
            result_path.write_text(json.dumps(result))
            self.assertEqual(validate(pkgs, base), digest)
            result['checks']['newest_kernel'] = False
            result_path.write_text(json.dumps(result))
            with self.assertRaises(ValueError): validate(pkgs, base)
            result['checks']['newest_kernel'] = True
            result['timestamp'] = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
            result_path.write_text(json.dumps(result))
            with self.assertRaises(ValueError): validate(pkgs, base)
            pkg.write_bytes(b'two')
            with self.assertRaises(ValueError): validate(pkgs, base)

if __name__ == '__main__': unittest.main()
