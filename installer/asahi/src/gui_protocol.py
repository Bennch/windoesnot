"""Optional structured UI alongside the unchanged CLI path. Never log secrets."""
import json
import os
import re
import sys

PREFIX = '@@WDN@@'
enabled = os.environ.get('WINDOESNOT_GUI') == '1'
last_prompt = ''


def clean(text):
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(text))


def event(event_type, **values):
    if enabled:
        print('\n' + PREFIX + json.dumps(dict(type=event_type, **values), ensure_ascii=True), flush=True)


def request(label=None, kind='text', choices=None, default=None):
    event('prompt', label=clean(label or last_prompt or 'Continue'), kind=kind,
          choices=choices or [], default=default)
    line = sys.stdin.readline()
    if not line:
        raise KeyboardInterrupt('GUI disconnected')
    value = line.rstrip('\r\n')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Control characters are not allowed in responses')
    return value
