"""Logical desktop geometry shared by startup and monitor-change handling."""


def logical_bounds(monitor):
    scale = float(monitor.get('scale', 1))
    if scale <= 0:
        raise ValueError('Invalid monitor scale')
    w, h = monitor['width'], monitor['height']
    if int(monitor.get('transform', 0)) % 2:
        w, h = h, w
    return round(w / scale), round(h / scale)


def window_rules(monitor, settings):
    width, height = logical_bounds(monitor)
    reserved = monitor.get('reserved') or [0, 0, 0, 0]
    left, top, right, bottom = [max(0, round(x)) for x in reserved]
    bottom = max(45, bottom)
    usable_w, usable_h = max(1, width - left - right), max(1, height - top - bottom)
    margin = min(8, usable_w // 10, usable_h // 10)
    available_w, available_h = max(1, usable_w - 2 * margin), max(1, usable_h - 2 * margin)
    align_left = settings.get('taskbarAlignment') == 'left'
    sizes = {
        'startmenu-config': (605 if settings.get('startMenuSidebarPosition') == 'hidden' else 820, 720, 'bottom'),
        'settings-config': (900, 700, 'bottom'),
        'calendar-config': (320, 360, 'right'),
        'audio-config': (320, 400, 'right'),
        'bluetooth-config': (320, 450, 'right'),
        'network-config': (320, 500, 'right'),
        'battery-config': (320, 360, 'right'),
        'nearby-config': (400, 580, 'right'),
        # Seed the rule before the first context-menu click.  The click handler
        # still supplies the icon-specific position and actual menu height.
        'appcontextmenu-config': (220, 129, 'bottom'),
        'docker-config': (340, 420, 'right'),
        'ollama-config': (360, 480, 'right'),
        'mediaplayer-config': (853, 500, 'top'),
        'colorpalette-config': (400, 480, 'center'),
        'search-config': (640, 480, 'center'),
        'copilot-config-pinned': (1100, 760, 'bottom'),
    }
    rules = {}
    for name, (desired_w, desired_h, anchor) in sizes.items():
        w, h = min(desired_w, available_w), min(desired_h, available_h)
        x = left + (usable_w - w) // 2
        y = top + (usable_h - h) // 2
        if anchor in ('bottom', 'right'):
            # Bottom panels meet the taskbar edge without a visible gap.
            y = top + usable_h - h
        if anchor == 'bottom' and align_left:
            x = left + margin
        if anchor == 'right':
            x = left + usable_w - w - margin
        if anchor == 'top':
            y = top
        rules[name] = {'size': [w, h], 'move': [x, y], 'monitor': monitor['name'], 'center': False}
    return {'primary_monitor': monitor['name'], 'width': width, 'height': height, 'rules': rules}
