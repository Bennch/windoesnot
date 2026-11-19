#!/usr/bin/env python3
"""Search window logic (SearchLogic.js, evaluated with node): app ranking with usage, calculator without eval, units."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

SRC = Path(__file__).resolve().parents[1] / 'desktop/config/quickshell/default/SearchLogic.js'
if shutil.which('node') is None:
    print('SKIP: node is not installed')
    sys.exit(0)
script = SRC.read_text().replace('.pragma library', '') + '''
const now = Date.now();
const apps = [{name:'Firefox',cmd:'firefox'},{name:'Visual Studio Code',cmd:'code'},{name:'Files',cmd:'nautilus'},
              {name:'Firefox ESR',cmd:'firefox-esr'},{name:'Text Editor',cmd:'gnome-text-editor'}];
const names = (q, u) => rankApps(apps, q, u || {}, 5, now).map(a => a.name);
const out = {
  prefix: names('fire'), initials: names('vsc'), fuzzy: names('ffx'), word: names('edit'), command: names('nautilus'),
  none: names('zzzz'), accent: rankApps([{name:'Café',cmd:'cafe'}], 'cafe', {}, 3, now).length,
  usageWins: names('fi', {Files: {c: 5, t: now}})[0],
  recents: recentApps(apps, {Files: {c: 5, t: now}, Firefox: {c: 1, t: now - 40*86400000}}, 5, now).map(a => a.name),
  recorded: recordUse({}, 'Files', now), many: Object.keys(recordUse(Object.fromEntries(Array.from({length: 250}, (_, i) => ['a'+i, {c:1,t:now}])), 'x', now)).length,
  calc: ['2+2','sqrt(16)','2^10','100+10%','20% of 150','(1+2)*3','1,5*2','10/4','-3+5','max(3,9)','5','2**3','alert(1)','1/0','process.exit()','1+','()'].map(answer),
  units: ['5 km in mi','100 c to f','1 gib in mb','2 h in min','10 kg to lb','3 foo to bar'].map(answer),
};
console.log(JSON.stringify(out));
'''
got = json.loads(subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True).stdout)
assert got['prefix'][:2] == ['Firefox', 'Firefox ESR'], got['prefix']
assert got['initials'] == ['Visual Studio Code'] and got['fuzzy'][0] == 'Firefox' and got['word'] == ['Text Editor']
assert got['command'] == ['Files'] and got['none'] == [] and got['accent'] == 1
assert got['usageWins'] == 'Files', 'an app started often outranks a weaker match'
assert got['recents'] == ['Files', 'Firefox'], got['recents']
assert got['recorded']['Files']['c'] == 1 and got['many'] == 200
assert got['calc'] == ['4', '4', '1024', '110', '30', '9', '3', '2.5', '2', '9', '', '', '', '', '', '', ''], got['calc']
assert got['units'][:5] == ['3.1068559612 mi', '212 °F', '1073.741824 mb', '120 min', '22.0462262185 lb'] and got['units'][5] == '', got['units']
print('PASS: search ranking, calculator and units')
