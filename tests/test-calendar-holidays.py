#!/usr/bin/env python3
"""Holiday dates of the calendar (Holidays.js) against known 2026/2027 dates, evaluated with node."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'desktop/config/quickshell/default/calendar/Holidays.js'
if shutil.which('node') is None:
    print('SKIP: node is not installed')
    sys.exit(0)
script = SRC.read_text().replace('.pragma library', '') + '''
const out = {};
const pick = (y, r, k) => { const e = holidays(y, r)[k]; return e ? e.de + '|' + e.kind : null; };
out.de_goodfriday = pick(2026, 'DE', '4-3'); out.de_easterMonday = pick(2026, 'DE', '4-6');
out.de_ascension = pick(2026, 'DE', '5-14'); out.de_whitMonday = pick(2026, 'DE', '5-25');
out.de_corpus = pick(2026, 'DE', '6-4'); out.de_unity = pick(2026, 'DE', '10-3');
out.de_repentance = pick(2026, 'DE', '11-18'); out.de_mothers = pick(2026, 'DE', '5-10');
out.de_goodfriday27 = pick(2027, 'DE', '3-26');
out.us_thanksgiving = pick(2026, 'US', '11-26'); out.us_memorial = pick(2026, 'US', '5-25'); out.us_labor = pick(2026, 'US', '9-7');
out.gb_summer = pick(2026, 'GB', '8-31'); out.gb_early = pick(2026, 'GB', '5-4');
out.at_national = pick(2026, 'AT', '10-26'); out.ch_national = pick(2026, 'CH', '8-1'); out.fr_bastille = pick(2026, 'FR', '7-14');
out.regions = [regionFor('de_DE.UTF-8', 'de'), regionFor('en_US', 'en'), regionFor('fr_CA', 'en'), regionFor('', 'de'), regionFor('en_GB', 'en')];
console.log(JSON.stringify(out));
'''
result = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True)
got = json.loads(result.stdout)
want = {
    'de_goodfriday': 'Karfreitag|public', 'de_easterMonday': 'Ostermontag|public', 'de_ascension': 'Christi Himmelfahrt|public',
    'de_whitMonday': 'Pfingstmontag|public', 'de_corpus': 'Fronleichnam|regional', 'de_unity': 'Tag der Deutschen Einheit|public',
    'de_repentance': 'Buß- und Bettag|regional', 'de_mothers': 'Muttertag|observance', 'de_goodfriday27': 'Karfreitag|public',
    'us_thanksgiving': 'Thanksgiving|public', 'us_memorial': 'Memorial Day|public', 'us_labor': 'Labor Day|public',
    'gb_summer': 'Summer Bank Holiday|public', 'gb_early': 'Early May Bank Holiday|public',
    'at_national': 'Nationalfeiertag|public', 'ch_national': 'Bundesfeier|public', 'fr_bastille': 'Nationalfeiertag (Fête nationale)|public',
    'regions': ['DE', 'US', 'GLOBAL', 'DE', 'GB'],
}
bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
assert not bad, bad
print('PASS: calendar holidays')
