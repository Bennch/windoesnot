#!/usr/bin/env python3
"""
Helper script to update replace.qml overrides safely
Usage: python3 update_replace.py save "App Name" "icon/path" "command" true/false
       python3 update_replace.py delete "App Name"
"""
import sys
import re
import json

def read_replace_file():
    with open('replace.qml', 'r') as f:
        return f.read()

def write_replace_file(content):
    with open('replace.qml', 'w') as f:
        f.write(content)

def save_override(app_name, icon, cmd, custom_icon):
    content = read_replace_file()

    # Find the overrides section
    pattern = r'(property var overrides: \(\{)(.*?)(\}\))'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        print("Error: Could not find overrides section", file=sys.stderr)
        return False

    before = content[:match.start()]
    overrides_content = match.group(2)
    after = content[match.end():]

    # Remove existing entry if it exists
    app_pattern = rf'^\s*"{re.escape(app_name)}":\s*\{{.*?\}},?\n?'
    overrides_content = re.sub(app_pattern, '', overrides_content, flags=re.MULTILINE | re.DOTALL)

    # Create new entry
    custom_icon_str = "true" if custom_icon == "true" else "false"
    new_entry = f'''        "{app_name}": {{
            icon: "{icon}",
            cmd: "{cmd}",
            customIcon: {custom_icon_str}
        }},
'''

    # Find insertion point (before comment line)
    comment_pos = overrides_content.find('// Weitere Overrides')
    if comment_pos != -1:
        overrides_content = overrides_content[:comment_pos] + new_entry + overrides_content[comment_pos:]
    else:
        # Add at the end
        overrides_content = overrides_content.rstrip() + '\n' + new_entry

    # Reconstruct file
    new_content = before + match.group(1) + overrides_content + match.group(3) + after
    write_replace_file(new_content)
    print("Override saved successfully")
    return True

def delete_override(app_name):
    content = read_replace_file()

    # Remove the app entry
    app_pattern = rf'^\s*"{re.escape(app_name)}":\s*\{{[^}}]*\}},?\n?'
    new_content = re.sub(app_pattern, '', content, flags=re.MULTILINE)

    write_replace_file(new_content)
    print("Override deleted successfully")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1]

    if action == 'save':
        if len(sys.argv) != 6:
            print("Error: save requires 4 arguments", file=sys.stderr)
            sys.exit(1)
        save_override(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif action == 'delete':
        if len(sys.argv) != 3:
            print("Error: delete requires 1 argument", file=sys.stderr)
            sys.exit(1)
        delete_override(sys.argv[2])
    else:
        print(f"Error: unknown action '{action}'", file=sys.stderr)
        sys.exit(1)
