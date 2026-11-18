"""Stable identity and fail-closed validation for update gate evidence."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

REQUIRED = {'install_offline', 'test_repo', 'regular_syu', 'target_versions',
            'newest_kernel', 'boot_mounted', 'configerrors', 'failed_units', 'personal_sha256'}

def package_set(directory):
    paths = sorted(Path(directory).glob('*.pkg.tar.*'))
    paths = [p for p in paths if p.is_file() and not p.name.endswith('.sig')]
    if not paths:
        raise ValueError('Paketordner enthält keine Paketarchive')
    h = hashlib.sha256()
    for path in paths:
        h.update(path.name.encode() + b'\0')
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
        h.update(b'\0')
    return h.hexdigest()

def validate(directory, result_dir, now=None):
    digest = package_set(directory)
    path = Path(result_dir) / (digest + '.json')
    try:
        data = json.loads(path.read_text())
        stamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        age = (now or datetime.now(timezone.utc)) - stamp
        if not timedelta(0) <= age < timedelta(hours=24):
            raise ValueError('Ergebnis ist älter als 24 Stunden oder liegt in der Zukunft')
        if data['package_set_sha256'] != digest or data['exit_code'] != 0:
            raise ValueError('Paketsatz oder Exitcode stimmt nicht')
        if not all(data['checks'].get(name) is True for name in REQUIRED):
            raise ValueError('Prüfungen unvollständig oder fehlgeschlagen')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f'Update-Gate fehlt oder ist ungültig ({path}): {exc}') from exc
    return digest
