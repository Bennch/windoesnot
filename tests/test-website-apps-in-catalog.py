#!/usr/bin/env python3
"""Every app the website advertises (use cards on the home page, both languages) exists in the installer's software catalog,
so the installer and the Store hand-off can find it. A new chip without a catalog entry fails here."""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
catalog = {a['id']: a for a in json.loads((ROOT / 'iso/software/catalog.json').read_text())['apps']}
# Website chip text -> catalog id (the chip text is what visitors read; the id is what the installer offers)
ALIASES = {'Steam': 'steam', 'Lutris': 'lutris', 'Heroic': 'heroic-games-launcher', 'Discord': 'discord', 'Proton': 'protonup-qt',
           'LibreOffice': 'libreoffice', 'Thunderbird': 'thunderbird', 'Nextcloud': 'nextcloud-client', 'Obsidian': 'obsidian',
           'GIMP': 'gimp', 'Krita': 'krita', 'Inkscape': 'inkscape', 'ArtCraft': 'artcraft-launcher', 'DaVinci Resolve': 'davinci-resolve',
           'Netflix': 'netflix', 'Spotify': 'spotify-launcher', 'Prime Video': 'prime-video', 'Disney+': 'disney-plus',
           'YouTube Music': 'youtube-music', 'VSCode': 'code', 'Git': 'git', 'Wireshark': 'wireshark-qt', 'DBeaver': 'dbeaver',
           'FileZilla': 'filezilla', 'Sublime Text': 'sublime-text', 'VMware Workstation': 'vmware-workstation', 'Ollama': 'ollama',
           'Alpaca': 'alpaca', 'Claude Code': 'claude-code', 'Codex CLI': 'codex-cli'}
seen = set()
for page in ('content/home-einfach.html', 'content/en/home-einfach.html'):
    text = (ROOT / 'website' / page).read_text()
    for chips in re.findall(r'<div class="use-chips">(.*?)</div>', text, re.S):
        for chip in re.findall(r'<span>(.*?)</span>', chips, re.S):
            name = re.sub(r'<[^>]+>', '', chip).strip()
            # chip badges ("A", "D", "P") are separate letters in front of the name
            name = next((n for n in sorted(ALIASES, key=len, reverse=True) if name.endswith(n)), name)
            assert name in ALIASES, f'{page}: "{name}" is advertised but has no entry in ALIASES (add it to the catalog first)'
            assert ALIASES[name] in catalog, f'{page}: "{name}" -> {ALIASES[name]} is missing in iso/software/catalog.json'
            seen.add(name)
assert len(seen) == len(ALIASES), set(ALIASES) - seen
print('PASS: all %d apps advertised on the website are in the installer catalog' % len(seen))
