#!/usr/bin/env python3
"""Fail-closed evaluator for evidence from the isolated update-hook VM.

This is a hook experiment, not the signed full-update release gate. Pass a JSON
file containing the observed transaction log and measurements; missing evidence
is always a failure. No machine is started or modified by this evaluator.
"""
import argparse
import json
from pathlib import Path


def evaluate(e):
    log = e.get('pacman_log', '')
    pre = log.find('Checking WinDoesNot boot filesystem before update')
    post = log.find('Validating WinDoesNot boot entries')
    kernel_hook = log.find('Updating linux initcpios')
    boots = e.get('reboots', [])
    checks = {
        'transaction_succeeded': e.get('transaction_exit') == 0,
        'hook_order': pre >= 0 and post > pre and kernel_hook > pre and post > kernel_hook,
        'old_entries_removed': e.get('old_entries_after') == [],
        'default_valid': e.get('default_valid') is True,
        'two_new_boots': len(boots) == 2 and len({b.get('boot_id') for b in boots} | {e.get('baseline_boot_id')}) == 3 and all(b.get('boot_id') for b in boots) and bool(e.get('baseline_boot_id')),
        'new_kernel': bool(e.get('old_kernel')) and bool(e.get('new_kernel')) and e['old_kernel'] != e['new_kernel'] and len(boots) == 2 and all(b.get('kernel') == e['new_kernel'] for b in boots),
        'negative_control': e.get('negative_control_invariant_failed') is True,
        'unmounted_pre_guard': e.get('unmounted_pre_guard_exit', 0) != 0 and e.get('unmounted_package_unchanged') is True,
    }
    return {'scope': 'manual hook experiment; not a release gate', 'vm_automated': False, 'passed': all(checks.values()), 'checks': checks}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('evidence', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    result = evaluate(json.loads(a.evidence.read_text()))
    output = json.dumps(result, indent=2) + '\n'
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(output)
    print(output, end='')
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
