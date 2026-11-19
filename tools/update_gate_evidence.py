"""Validate exact VM observations before accepting update-gate evidence."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from update_gate_runner import hook_order

POSITIVE_CHECKS = {'manager_hook_intact', 'package_files_intact', 'install_offline', 'test_repo', 'regular_syu', 'hook_order', 'post_hook_status',
                   'target_versions', 'newest_kernel', 'boot_mounted', 'default_valid', 'old_entries_removed',
                   'failed_units', 'personal_sha256', 'desktop_plugins', 'configerrors', 'no_pending_updates',
                   'two_new_boots', 'kernel_changed', 'package_set_unchanged'}
GUEST_CHECKS = {'manager_hook_intact', 'package_files_intact', 'target_versions', 'newest_kernel', 'boot_mounted', 'default_valid', 'old_entries_removed',
                'failed_units', 'personal_sha256', 'desktop_plugins', 'configerrors', 'no_pending_updates'}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fresh(timestamp, now):
    stamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return timedelta(0) <= now - stamp < timedelta(hours=24)


def inspect(result_path, digest, kind, now=None):
    now = now or datetime.now(timezone.utc)
    result_path = Path(result_path).resolve(strict=True)
    result = json.loads(result_path.read_text())
    log_path = result_path.with_name('update.log')
    log = log_path.read_text(errors='replace')
    if result.get('package_set_sha256') != digest or not fresh(result['timestamp'], now):
        raise ValueError(f'{kind}: package hash or timestamp mismatch')
    if result.get('cleanup_error'):
        raise ValueError(f'{kind}: VM cleanup failed')
    checks = result.get('checks', {})
    if kind == 'positive':
        if result.get('passed') is not True or not all(checks.get(k) is True for k in POSITIVE_CHECKS):
            raise ValueError('positive: missing or failed checks')
        boots = result.get('reboots', [])
        if len(boots) != 2 or len({result.get('baseline_boot_id'), *(b.get('boot_id') for b in boots)}) != 3 or any(not b.get('boot_id') for b in boots) or not result.get('baseline_boot_id'):
            raise ValueError('positive: missing or repeated boot IDs')
        if any(not b.get('kernel') or b['kernel'] == result.get('baseline_kernel') or 'lts' in b['kernel'] or not all(b.get('checks', {}).get(k) is True for k in GUEST_CHECKS) for b in boots):
            raise ValueError('positive: invalid reboot observations')
        if result.get('job', {}).get('steps') != {'bootstrap': 0, 'update': 0}:
            raise ValueError('positive: transaction did not complete')
        if not hook_order(log, result.get('configuration', 'A')):
            raise ValueError('positive: hook sequence missing')
    else:
        job = result.get('job', {}).get('steps', {})
        if result.get('passed') is not False or result.get('mutation') != kind or result.get('mutation_active') is not True:
            raise ValueError(f'{kind}: mutation was not active and detected')
        if job.get('bootstrap') != 0:
            raise ValueError(f'{kind}: bootstrap failed')
        if kind == 'A':
            ok = job.get('update') not in (None, 0) and '/usr/bin/windoesnot-update' in log and 'exists in filesystem' in log
        elif kind == 'B':
            ok = job.get('update') not in (None, 0) and 'exit status 73' in log
        elif kind == 'C':
            ok = (job.get('update') == 0 and len(result.get('reboots', [])) == 2
                  and result.get('error') == 'one or more update assertions failed'
                  and checks.get('hook_order') is False and checks.get('post_hook_status') is False
                  and all(checks.get(k) is True for k in POSITIVE_CHECKS - {'hook_order', 'post_hook_status'}))
        else:
            raise ValueError('unknown evidence kind')
        if not ok:
            raise ValueError(f'{kind}: expected failure cause not demonstrated')
    return {'result': str(result_path), 'result_sha256': sha256(result_path),
            'log': str(log_path), 'log_sha256': sha256(log_path)}


def inspect_index(data, digest, now=None):
    now = now or datetime.now(timezone.utc)
    if data.get('schema') != 3 or not fresh(data['timestamp'], now):
        raise ValueError('missing matrix schema or expired gate result')
    if data.get('package_set_sha256') != digest or data.get('exit_code') != 0:
        raise ValueError('package hash or exit code mismatch')
    for kind in ('positive', 'A', 'B', 'C'):
        stored = data['evidence'][kind]
        current = inspect(stored['result'], digest, kind, now)
        if stored != current:
            raise ValueError(f'{kind}: evidence bytes or paths changed')
    positive = json.loads(Path(data['evidence']['positive']['result']).read_text())
    iso = Path(data['iso']).resolve(strict=True)
    if sha256(iso) != data['iso_sha256'] or not any(
            Path(name).name == iso.name and value == data['iso_sha256']
            for name, value in positive['baseline_manifest']['files'].items()):
        raise ValueError('predecessor ISO does not match the baseline')
    matrix = data['matrix']
    if set(matrix) != {'A', 'B', 'C', 'D', 'E', 'F'}:
        raise ValueError('all six boot configurations are required')
    for config, item in matrix.items():
        stored = item['positive']
        if inspect(stored['result'], digest, 'positive', now) != stored:
            raise ValueError(f'{config}: evidence bytes or paths changed')
        result = json.loads(Path(stored['result']).read_text())
        if result.get('configuration') != config or result.get('checks', {}).get('pacman_install_remove') is not True:
            raise ValueError(f'{config}: boot configuration or package transaction missing')
        probe = Path(item['pacman_probe']).resolve(strict=True)
        if probe != Path(stored['result']).with_name('pacman-probe.log') or sha256(probe) != item['pacman_probe_sha256']:
            raise ValueError(f'{config}: package transaction log changed')
        probe_log = probe.read_text(errors='replace')
        installed = ('installing windoesnot-gate-probe' in probe_log or 'windoesnot-gate-probe wird installiert' in probe_log)
        removed = ('removing windoesnot-gate-probe' in probe_log or 'windoesnot-gate-probe wird entfernt' in probe_log)
        if 'Checking WinDoesNot boot filesystem before update' not in probe_log or not installed or not removed:
            raise ValueError(f'{config}: package guard, installation or removal missing')
        source = Path(item['iso']).resolve(strict=True)
        source_hash = sha256(source)
        if source_hash != item['iso_sha256'] or not any(Path(name).name == source.name and value == source_hash for name, value in result['baseline_manifest']['files'].items()):
            raise ValueError(f'{config}: predecessor ISO does not match baseline')
    if matrix['A']['positive'] != data['evidence']['positive']:
        raise ValueError('configuration A evidence does not match mutation set')
