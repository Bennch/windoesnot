#!/usr/bin/env python3
"""The gate must reject stale, unrelated or tampered VM evidence."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from update_gate_evidence import GUEST_CHECKS, POSITIVE_CHECKS, inspect, inspect_index, sha256
from update_gate_common import package_set, validate

class Evidence(unittest.TestCase):
    def test_exact_hash_freshness_and_failure_causes(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            packages = base / 'packages'; packages.mkdir()
            (packages / 'test.pkg.tar.zst').write_bytes(b'candidate')
            digest = package_set(packages)
            iso = base / 'old.iso'; iso.write_bytes(b'old iso')
            paths = {}
            for kind in ('positive', 'A', 'B', 'C'):
                directory = base / kind; directory.mkdir()
                data = {'timestamp': now.isoformat(), 'package_set_sha256': digest,
                        'passed': kind == 'positive', 'checks': {x: True for x in POSITIVE_CHECKS},
                        'job': {'steps': {'bootstrap': 0, 'update': 0 if kind in ('positive', 'C') else 1}},
                        'baseline_boot_id': 'old', 'baseline_kernel': 'old-kernel',
                        'reboots': [{'boot_id': 'new1', 'kernel': 'new-kernel', 'checks': {x: True for x in GUEST_CHECKS}},
                                    {'boot_id': 'new2', 'kernel': 'new-kernel', 'checks': {x: True for x in GUEST_CHECKS}}]}
                log = ('Checking WinDoesNot boot filesystem before update\nUpdating linux initcpios\n'
                       'Validating WinDoesNot boot entries')
                if kind == 'positive':
                    data['configuration'] = 'A'
                    data['checks']['pacman_install_remove'] = True
                    data['baseline_manifest'] = {'files': {'old.iso': sha256(iso)}}
                else:
                    data.update(mutation=kind, mutation_active=True)
                    if kind == 'A': log = '/usr/bin/windoesnot-update exists in filesystem'
                    if kind == 'B': log = 'exit status 73'
                    if kind == 'C':
                        data['error'] = 'one or more update assertions failed'
                        data['checks'].update(hook_order=False, post_hook_status=False)
                path = directory / 'result.json'; path.write_text(json.dumps(data))
                (directory / 'update.log').write_text(log)
                paths[kind] = path
            matrix = {}
            for config in 'ABCDEF':
                directory = base / ('positive-' + config); directory.mkdir()
                data = json.loads(paths['positive'].read_text()); data['configuration'] = config
                path = directory / 'result.json'; path.write_text(json.dumps(data))
                log = (paths['positive'].parent / 'update.log').read_text()
                if config != 'A':
                    log = log.replace('Checking WinDoesNot boot filesystem before update',
                                      'Kein systemd-boot-Layout; keine Änderung erforderlich.')
                (directory / 'update.log').write_text(log)
                probe = directory / 'pacman-probe.log'
                actions = ('windoesnot-gate-probe wird installiert\nwindoesnot-gate-probe wird entfernt'
                           if config == 'A' else 'installing windoesnot-gate-probe\nremoving windoesnot-gate-probe')
                probe.write_text('Checking WinDoesNot boot filesystem before update\n' + actions)
                matrix[config] = {'positive': inspect(path, digest, 'positive', now), 'iso': str(iso),
                                  'iso_sha256': sha256(iso), 'pacman_probe': str(probe), 'pacman_probe_sha256': sha256(probe)}
            paths['positive'] = base / 'positive-A' / 'result.json'
            index = {'schema': 3, 'timestamp': now.isoformat(), 'package_set_sha256': digest,
                     'exit_code': 0, 'iso': str(iso), 'iso_sha256': sha256(iso),
                     'checks': {x: True for x in POSITIVE_CHECKS},
                     'evidence': {k: inspect(v, digest, k, now) for k, v in paths.items()}, 'matrix': matrix}
            inspect_index(index, digest, now)
            (base / (digest + '.json')).write_text(json.dumps(index))
            self.assertEqual(validate(packages, base, now), digest)
            for omitted in 'ABCDEF':
                missing = dict(index, matrix={k: v for k, v in matrix.items() if k != omitted})
                with self.assertRaises(ValueError): inspect_index(missing, digest, now)
            with self.assertRaises(ValueError): inspect_index(dict(index, schema=2), digest, now)
            probe = base / 'positive-B' / 'pacman-probe.log'
            old_probe = probe.read_text(); probe.write_text('missing guard')
            matrix['B']['pacman_probe_sha256'] = sha256(probe)
            with self.assertRaises(ValueError): inspect_index(index, digest, now)
            probe.write_text(old_probe); matrix['B']['pacman_probe_sha256'] = sha256(probe)
            wrong = dict(matrix, B=matrix['A'])
            with self.assertRaises(ValueError): inspect_index(dict(index, matrix=wrong), digest, now)
            with self.assertRaises(ValueError): inspect_index(index, 'different', now)
            with self.assertRaises(ValueError): inspect_index(index, digest, now + timedelta(hours=25))
            (paths['A'].parent / 'update.log').write_text('network error')
            with self.assertRaises(ValueError): inspect_index(index, digest, now)
            iso.write_bytes(b'changed')
            with self.assertRaises(ValueError): inspect_index(index, digest, now)

if __name__ == '__main__': unittest.main()
