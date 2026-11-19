#!/usr/bin/env python3
"""Validate exact 29-to-32 VM evidence and record a short-lived package gate."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from update_gate_common import package_set, validate
from update_gate_evidence import inspect, inspect_index, sha256

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iso', required=True, type=Path, help='predecessor ISO used by the baseline')
    p.add_argument('--packages', required=True, type=Path, help='exact candidate package directory')
    p.add_argument('--positive', required=True, type=Path, help='successful VM result.json')
    p.add_argument('--positive-b', required=True, type=Path, help='UEFI GRUB VM result.json')
    p.add_argument('--positive-c', required=True, type=Path, help='BIOS GRUB VM result.json')
    p.add_argument('--iso-b', required=True, type=Path, help='UEFI GRUB predecessor ISO')
    p.add_argument('--iso-c', required=True, type=Path, help='BIOS GRUB predecessor ISO')
    for name in 'abc':
        p.add_argument('--mutation-' + name, required=True, type=Path, help='real mutation result.json')
    a = p.parse_args()
    try:
        iso = a.iso.resolve(strict=True)
        digest = package_set(a.packages)
        output = ROOT / 'out/update-gate' / (digest + '.json')
        # A failed recheck must not leave a previous success usable.
        output.unlink(missing_ok=True)
        now = datetime.now(timezone.utc)
        paths = {'positive': a.positive, 'A': a.mutation_a, 'B': a.mutation_b, 'C': a.mutation_c}
        evidence = {kind: inspect(path, digest, kind, now) for kind, path in paths.items()}
        positive = json.loads(Path(evidence['positive']['result']).read_text())
        matrix = {}
        for config, path, source_iso in [('A', a.positive, iso), ('B', a.positive_b, a.iso_b), ('C', a.positive_c, a.iso_c)]:
            positive_evidence = inspect(path, digest, 'positive', now)
            probe = Path(positive_evidence['result']).with_name('pacman-probe.log').resolve(strict=True)
            source_iso = source_iso.resolve(strict=True)
            matrix[config] = {'positive': positive_evidence, 'iso': str(source_iso), 'iso_sha256': sha256(source_iso),
                              'pacman_probe': str(probe), 'pacman_probe_sha256': sha256(probe)}
        result = {'schema': 3, 'timestamp': now.isoformat(), 'package_set_sha256': digest,
                  'exit_code': 0, 'iso': str(iso), 'iso_sha256': sha256(iso),
                  'checks': positive['checks'], 'evidence': evidence, 'matrix': matrix}
        inspect_index(result, digest, now)
        if package_set(a.packages) != digest:
            raise ValueError('package set changed while evidence was checked')
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + '.tmp')
        temporary.write_text(json.dumps(result, indent=2) + '\n')
        os.replace(temporary, output)
        try:
            validate(a.packages, output.parent, now)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        print(json.dumps({'status': 'PASS', 'package_set_sha256': digest, 'result': str(output),
                          'expires_in_hours': 24}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('FAIL: update gate evidence rejected: ' + str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
