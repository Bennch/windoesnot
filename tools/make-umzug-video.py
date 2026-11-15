#!/usr/bin/env python3
"""Render the WinDoesNot migration video from locally captured PNGs."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'desktop/share/sddm/themes/windoesnot/fonts/PlusJakartaSans-VariableFont_wght.ttf'
LOGO = ROOT / 'desktop/config/quickshell/default/img/brand/windoesnot-icon-512.png'
DEFAULTS = {'windows': 1.3, 'boot': 4, 'installer': 8, 'desktop': 6, 'end': 3}
TEXT = {
 'de': ['Linux zu nutzen oder zu installieren war nie einfacher.', 'Umzugstool unter Windows öffnen', 'Der Rechner startet WinDoesNot', 'Installieren in wenigen Minuten', 'Fertig: dein neuer Desktop', 'Dateien bleiben unverändert, wenn du neben Windows installierst.', 'Das Umzugstool ist offen'],
 'en': ['Using or installing Linux has never been easier.', 'Open the move tool on Windows', 'Your PC starts WinDoesNot', 'Install in a few minutes', 'Done: your new desktop', 'Your files stay untouched when you install next to Windows.', 'The move tool is open'],
}

def run(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)

def esc(s):
    return str(s).replace('\\', '\\\\').replace(':', r'\:').replace("'", r"'\''").replace('%', r'\%')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--footage', type=Path, default=ROOT/'deliverables/umzug-video/footage')
    p.add_argument('--out', type=Path, default=ROOT/'deliverables/umzug-video/out')
    p.add_argument('--only', choices=['reel','web','gif'])
    p.add_argument('--lang', choices=['de','en','both'], default='both')
    p.add_argument('--config', type=Path, help='JSON object with scene durations in seconds')
    p.add_argument('--preview-without-windows', action='store_true', help='Vorschau ohne Windows-Szene (nur zum Ansehen, nicht veroeffentlichen)')
    a = p.parse_args()
    durations = DEFAULTS.copy()
    if a.config:
        config = json.loads(a.config.read_text())
        if not isinstance(config, dict) or set(config) - set(durations):
            raise ValueError('Konfiguration enthält unbekannte Schlüssel')
        durations.update(config)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in durations.values()):
        raise ValueError('Alle Dauern müssen positive Zahlen sein')
    footage = a.footage.resolve()
    out = a.out.resolve()
    if out == footage or footage in out.parents or out in footage.parents:
        raise ValueError('Ausgabe und Eingabematerial müssen getrennte Ordner sein')
    windows = [(footage/'01-windows'/('windows-'+v+'.png'), 'Windows '+v) for v in ('7','8.1','10','11')]
    windows = [(f,n) for f,n in windows if f.is_file()]
    if not windows and not a.preview_without_windows:
        raise ValueError('01-windows: mindestens ein Windows-Bild fehlt')
    scenes = []
    for dirname, key in [('02-boot','boot'),('03-installer','installer'),('04-desktop','desktop')]:
        folder = footage/dirname
        frames = sorted(folder.glob('frame-[0-9][0-9][0-9][0-9].png'))
        if not frames:
            raise ValueError(f'{dirname}: keine Frames gefunden')
        try:
            fps = float((folder/'fps.txt').read_text().strip())
            if not math.isfinite(fps) or fps <= 0: raise ValueError()
        except (OSError, ValueError):
            raise ValueError(f'{dirname}: fps.txt fehlt oder enthält keine positive Bildrate') from None
        scenes.append((frames, durations[key]))
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='umzug-video-') as tmp:
        tmp = Path(tmp)
        # Explicit 30 fps sampling distributes the captured frames without interpolation.
        timeline = []
        for f, name in windows:
            timeline.append(([f], durations['windows'], 1, name))
        for i, (frames, duration) in enumerate(scenes, 2):
            timeline.append((frames, duration, i, ''))
        timeline.append(([LOGO], durations['end'], 5, ''))
        manifest = tmp/'frames.ffconcat'
        lines = ['ffconcat version 1.0']
        intervals = []
        cursor = 0
        for frames, duration, step, label in timeline:
            count = max(1, round(duration*30))
            start = cursor/30
            for j in range(count):
                frame = frames[min(len(frames)-1, j*len(frames)//count)]
                path = str(frame.resolve()).replace("'", "'\\''")
                lines.extend([f"file '{path}'", 'duration 0.033333333333'])
            cursor += count
            intervals.append((start, cursor/30, step, label))
        lines.append(f"file '{str(LOGO.resolve()).replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'")
        manifest.write_text('\n'.join(lines)+'\n')
        total = cursor/30
        for lang in (['de','en'] if a.lang == 'both' else [a.lang]):
            for kind in (['reel','web'] if a.only is None else (['web'] if a.only == 'gif' else [a.only])):
                portrait = kind == 'reel'
                w,h = (1080,1920) if portrait else (1920,1080)
                fw,fh = (960,600) if portrait else (1120,700)
                x,y = (60,520) if portrait else (400,180)
                # Rounded alpha mask and a blurred black silhouette give the footage a soft shadow.
                radius = 30
                alpha = f"if(lte(hypot(max({radius}-X,0)+max(X-(W-{radius}),0),max({radius}-Y,0)+max(Y-(H-{radius}),0)),{radius}),255,0)"
                filt = [f'[0:v]fps=30,scale={fw}:{fh}:force_original_aspect_ratio=decrease,pad={fw}:{fh}:(ow-iw)/2:(oh-ih)/2:color=0x161b25,format=rgba,geq=r=\'r(X,Y)\':g=\'g(X,Y)\':b=\'b(X,Y)\':a=\'{alpha}\',split=2[pic][shadow]',
                        f'[shadow]colorchannelmixer=rr=0:gg=0:bb=0:aa=0.55,boxblur=18:2[sh]',
                        f'color=c=0x10151e:s={w}x{h}:r=30:d={total}[bg]',
                        f'[bg][sh]overlay={x}:{y+14}[base]', f'[base][pic]overlay={x}:{y}[v0]']
                n = 0
                def draw(text, yy, size, color='white', enable=None):
                    nonlocal n
                    opt = f":enable='{enable}'" if enable else ''
                    filt.append(f"[v{n}]drawtext=fontfile='{esc(FONT)}':text='{esc(text)}':fontsize={size}:fontcolor={color}:x=(w-text_w)/2:y={yy}{opt}[v{n+1}]")
                    n += 1
                # Two lines avoid clipping the supplied title and end text.
                title = ['Linux zu nutzen oder zu installieren', 'war nie einfacher.'] if lang == 'de' else ['Using or installing Linux', 'has never been easier.']
                for j, line in enumerate(title): draw(line, (160 if portrait else 34)+j*(55 if portrait else 40), 44 if portrait else 34)
                for start,end,step,label in intervals:
                    enable = f'between(t,{start},{end-0.00001})'
                    if step < 5:
                        draw(TEXT[lang][step], 1450 if portrait else 940, 42 if portrait else 38, enable=enable)
                        if label:
                            draw(label, 1155 if portrait else 895, 36, '0xff6a2b', enable)
                            draw(TEXT[lang][6], 1205 if portrait else 860, 30, enable=enable)
                    else:
                        draw('windoesnot.me', 1200 if portrait else 885, 48, '0xff6a2b', enable)
                        chunks = (['Dateien bleiben unverändert,', 'wenn du neben Windows installierst.'] if lang == 'de' else ['Your files stay untouched', 'when you install next to Windows.'])
                        for j, line in enumerate(chunks): draw(line, (1390 if portrait else 950)+j*42, 32, enable=enable)
                for i in range(1,5):
                    for active in (False, True):
                        expr = '+'.join(f'between(t,{s},{e-0.00001})' for s,e,step,_ in intervals if (step == i) == active)
                        if expr:
                            px = w//2 + (i-2.5)*48
                            filt.append(f"[v{n}]drawbox=x={int(px)}:y={1530 if portrait else 1020}:w=18:h=18:color={'0xff6a2b' if active else '0x6d7684'}:t=fill:enable='{expr}'[v{n+1}]")
                            n += 1
                for boundary in [end for _, end, step, _ in intervals[:-1] if step == 1]:
                    fade = min(0.15, durations['windows']/3)
                    filt.append(f'[v{n}]fade=t=out:st={boundary-fade}:d={fade},fade=t=in:st={boundary}:d={fade}[v{n+1}]')
                    n += 1
                target = out/f'umzug-{kind}-{"9x16" if portrait else "16x9"}-{lang}.mp4'
                if a.only == 'gif': target = tmp/f'{lang}.mp4'
                command = ['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(manifest),'-filter_complex',';'.join(filt),'-map',f'[v{n}]','-t',str(total),'-an','-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart','-threads','4',str(target)]
                run(command)
                if kind == 'web':
                    if a.only != 'gif':
                        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(target),'-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','8','-crf','34','-b:v','0','-threads','4',str(target.with_suffix('.webm'))])
                    if a.only in (None, 'gif'):
                        gif = out/f'umzug-{lang}.gif'
                        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(target),'-filter_complex','fps=12,scale=720:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:diff_mode=rectangle','-loop','0',str(gif)])
                        if gif.stat().st_size >= 8_000_000:
                            gif.unlink()
                            raise ValueError(f'{gif.name} ist größer als 8 MB; Szenendauern verkürzen')
                    if a.only is None:
                        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(intervals[-2][0]),'-i',str(target),'-frames:v','1',str(out/f'poster-{lang}.png')])
    return 0

if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Fehler: {exc}', file=sys.stderr)
        sys.exit(1)
