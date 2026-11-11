"""Stage quiet, recoverable boot presentation in generated profiles, never the host."""
from pathlib import Path
import base64
import re
import shutil
import subprocess

KERNEL_PARAMS=['quiet','splash','loglevel=3','systemd.show_status=error','rd.systemd.show_status=error','udev.log_level=3','rd.udev.log_level=3']
SERIAL_PARAM='plymouth.ignore-serial-consoles'

def quiet_commandline(line):
    words=line.split()
    keys={word.split('=',1)[0] for word in KERNEL_PARAMS}
    words=[word for word in words if word.split('=',1)[0] not in keys and word!=SERIAL_PARAM]
    # Keep serial diagnostics available but put tty0 last so /dev/console and
    # failed-boot diagnostics appear on the physical screen too.
    if 'console=tty0' in words:
        words.remove('console=tty0');words.append('console=tty0')
    # Plymouth falls back to its text view when any console= is serial.
    extra=[SERIAL_PARAM] if any(word.startswith('console=ttyS') for word in words) else []
    return ' '.join(words+KERNEL_PARAMS+extra)

def add_hook(text):
    def replace(match):
        hooks=match.group(2).split()
        if 'plymouth' not in hooks:
            anchor='kms' if 'kms' in hooks else ('udev' if 'udev' in hooks else 'systemd')
            hooks.insert(hooks.index(anchor)+1,'plymouth')
        if 'windoesnot-boot-errors' not in hooks:
            hooks.insert(hooks.index('plymouth')+1,'windoesnot-boot-errors')
        return match.group(1)+' '.join(hooks)+')'
    result,count=re.subn(r'^(HOOKS=\()(.*?)(?:\))$',replace,text,flags=re.M)
    if count!=1: raise ValueError('Expected one mkinitcpio HOOKS array')
    return result

def stage(root,assets,logo):
    root=Path(root).resolve();assets=Path(assets)
    if root==Path('/'): raise ValueError('Refusing to modify the running host')
    def write(name,text):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    # Use the image's own Plymouth assets, not copies of the host's plugin ABI.
    write('etc/plymouth/plymouthd.conf','[Daemon]\nTheme=windoesnot\nShowDelay=0\nDeviceTimeout=8\n')
    theme=root/'usr/share/plymouth/themes/windoesnot';theme.mkdir(parents=True,exist_ok=True)
    shutil.copy2(assets/'windoesnot.plymouth',theme/'windoesnot.plymouth')
    image=base64.b64encode(Path(logo).read_bytes()).decode()
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="480" height="90"><image width="480" height="90" preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,{image}"/></svg>'
    subprocess.run(['rsvg-convert','-o',str(theme/'watermark.png')],input=svg.encode(),check=True)
    write('usr/lib/windoesnot/boot-error',(assets/'boot-error').read_text())
    (root/'usr/lib/windoesnot/boot-error').chmod(0o755)
    write('usr/lib/systemd/system/windoesnot-boot-error@.service',(assets/'windoesnot-boot-error@.service').read_text())
    for kind in ['service','mount','swap']:
        write('usr/lib/systemd/system/'+kind+'.d/90-windoesnot-boot-errors.conf','[Unit]\nOnFailure=windoesnot-boot-error@%n.service\n')
    write('usr/lib/systemd/system/windoesnot-boot-error@.service.d/99-no-recursion.conf','[Unit]\nOnFailure=\n')
    write('usr/lib/initcpio/install/windoesnot-boot-errors','''#!/usr/bin/bash
build() {
    if command -v add_systemd_unit >/dev/null; then
        add_binary /usr/bin/bash
        add_binary /usr/bin/journalctl
        add_file /usr/lib/windoesnot/boot-error
        add_systemd_unit windoesnot-boot-error@.service
        add_file /usr/lib/systemd/system/windoesnot-boot-error@.service.d/99-no-recursion.conf
        for kind in service mount swap; do
            add_file "/usr/lib/systemd/system/$kind.d/90-windoesnot-boot-errors.conf"
        done
    fi
}
help() { echo 'Reveal the console when a systemd boot job fails while Plymouth is active.'; }
''')

def finish_theme(root):
    """Run inside the image/VM after its Plymouth package has been installed."""
    root=Path(root)
    source=root/'usr/share/plymouth/themes/spinner'
    target=root/'usr/share/plymouth/themes/windoesnot'
    for path in source.glob('*.png'):
        if path.name!='watermark.png': shutil.copy2(path,target/path.name)
    if not list(target.glob('throbber-*.png')): raise RuntimeError('Image Plymouth spinner assets missing')
