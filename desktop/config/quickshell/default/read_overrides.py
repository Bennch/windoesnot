#!/usr/bin/env python3
"""
Reads overrides from replace.qml and outputs as JSON
"""
import json
import re

def parse_replace_qml():
    with open('replace.qml', 'r') as f:
        content = f.read()

    # Find the overrides object
    pattern = r'property var overrides: \(\{(.*?)\}\)'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        print(json.dumps({}))
        return

    overrides_text = match.group(1)
    overrides = {}

    # Parse each app entry
    # Pattern: "AppName": { icon: "...", cmd: "...", customIcon: true/false }
    app_pattern = r'"([^"]+)":\s*\{([^}]+)\}'

    for app_match in re.finditer(app_pattern, overrides_text):
        app_name = app_match.group(1)
        app_content = app_match.group(2)

        # Parse properties
        icon_match = re.search(r'icon:\s*"([^"]*)"', app_content)
        cmd_match = re.search(r'cmd:\s*"([^"]*)"', app_content)
        custom_icon_match = re.search(r'customIcon:\s*(true|false)', app_content)

        overrides[app_name] = {
            'icon': icon_match.group(1) if icon_match else '',
            'cmd': cmd_match.group(1) if cmd_match else '',
            'customIcon': custom_icon_match.group(1) == 'true' if custom_icon_match else False
        }

    print(json.dumps(overrides))

if __name__ == '__main__':
    parse_replace_qml()
