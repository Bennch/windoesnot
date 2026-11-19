#!/usr/bin/env python3
"""Evaluate manual hook evidence or run an isolated 29-to-32 VM experiment.

Neither mode grants release approval. The run mode creates and deletes its own
VM overlay; the legacy evidence evaluator does not start a machine.
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
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ('install', 'update', 'verify', 'run'):
        from update_gate_runner import Runner
        parser = argparse.ArgumentParser(description='Run isolated 29-to-32 update experiment')
        parser.add_argument('stage', choices=['install', 'update', 'verify', 'run'])
        parser.add_argument('--packages', type=Path)
        parser.add_argument('--configuration', choices=['A', 'B', 'C'], default='A')
        parser.add_argument('--vm-name', help='owned VM name returned by install')
        args = parser.parse_args()
        if args.stage in ('install', 'run'):
            if not args.packages or args.vm_name:
                parser.error('install/run require --packages and do not accept --vm-name')
            runner = Runner(args.packages, configuration=args.configuration)
        else:
            if not args.vm_name or args.packages:
                parser.error('update/verify require --vm-name and do not accept --packages')
            runner = Runner.attach(args.vm_name)
        if args.stage == 'run':
            result = runner.execute()
            print(json.dumps(result, indent=2))
            return 0 if result['passed'] else 1
        try:
            if args.stage == 'install':
                runner.install()
                runner.checkpoint('installed')
            elif args.stage == 'update':
                if runner.phase != 'installed':
                    raise RuntimeError('update requires the installed stage')
                try:
                    runner.update()
                finally:
                    runner.stop_server()
                runner.checkpoint('updated')
            else:
                if runner.phase != 'updated':
                    raise RuntimeError('verify requires a successful update stage')
                runner.verify()
                runner.result['passed'] = True
                runner.cleanup()
                runner.checkpoint('verified')
            print(json.dumps({'vm': runner.name, 'stage': runner.phase,
                              'result': runner.result}, indent=2))
            return 0
        except Exception as exc:
            runner.result['passed'] = False
            runner.result['error'] = str(exc)
            try:
                runner.cleanup()
            finally:
                runner.checkpoint('failed')
            print(json.dumps(runner.result, indent=2))
            return 1
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
