#!/usr/bin/env python3
"""Render the WinDoesNot migration video from locally captured PNGs."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'desktop/share/sddm/themes/windoesnot/fonts/PlusJakartaSans-VariableFont_wght.ttf'
LOGO = ROOT / 'desktop/config/quickshell/default/img/brand/windoesnot-logo-hell.png'
DEFAULTS = {'windows': 1.3, 'boot': 6, 'installer': 9, 'desktop': 6, 'end': 3}
TEXT = {
 'de': ['Linux zu nutzen oder zu installieren war nie einfacher.', 'Umzugstool unter Windows öffnen', 'Installieren in wenigen Minuten', 'Neustart: dein neues System startet', 'Fertig: dein neuer Desktop', 'Dateien bleiben unverändert, wenn du neben Windows installierst.', 'Das Umzugstool ist offen'],
 'en': ['Using or installing Linux has never been easier.', 'Open the move tool on Windows', 'Install in a few minutes', 'Restart: your new system starts', 'Done: your new desktop', 'Your files stay untouched when you install next to Windows.', 'The move tool is open'],
}

def run(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)

def esc(s):
    return str(s).replace('\\', '\\\\').replace(':', r'\:').replace("'", r"'\''").replace('%', r'\%')

def visible_frames(frames):
    result = []
    for path in frames:
        with Image.open(path) as image:
            image = image.convert('RGB')
            image.thumbnail((64, 64))
            if sum(ImageStat.Stat(image).mean) / 3 >= 2:
                result.append(path)
    return result

def detect_beats(music):
    """Low-frequency onset strength and an autocorrelation-smoothed beat grid."""
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(music), '-ac', '1', '-ar', '44100', '-f', 'f32le', '-'])
    samples = np.frombuffer(raw, dtype='<f4')
    hop, size, rate = 220, 2048, 44100
    if len(samples) < size:
        raise ValueError('Musikdatei ist zu kurz')
    # FFT low-pass, then positive spectral flux and an energy envelope.
    blocks = np.lib.stride_tricks.sliding_window_view(samples, size)[::hop]
    spectrum = np.abs(np.fft.rfft(blocks * np.hanning(size), axis=1))
    low = spectrum[:, np.fft.rfftfreq(size, 1/rate) < 150]
    energy = np.sqrt(np.sum(low ** 2, axis=1))
    flux = np.maximum(0, np.diff(low, axis=0, prepend=low[:1])).sum(axis=1)
    onset = np.maximum(0, np.diff(energy, prepend=energy[0])) + flux * 0.15
    # Frame windows look ahead; position the onset at their leading edge.
    threshold = np.maximum(np.convolve(onset, np.ones(101)/101, mode='same') * 1.5, onset.max() * 0.08)
    candidates = np.flatnonzero((onset[1:-1] > onset[:-2]) & (onset[1:-1] >= onset[2:]) & (onset[1:-1] > threshold[1:-1])) + 1
    peaks = []
    for i in sorted(candidates, key=lambda j: onset[j], reverse=True):
        if all(abs(i-j) >= int(.25*rate/hop) for j in peaks): peaks.append(i)
    peaks.sort()
    if len(peaks) < 2: raise ValueError('Zu wenige Beats in der Musik erkannt')
    # Autocorrelation finds tempo; restrict to a practical 75–180 BPM range.
    centered = onset - onset.mean()
    nfft = 1 << (2*len(centered)-1).bit_length()
    spec = np.fft.rfft(centered, nfft)
    corr = np.fft.irfft(spec * spec.conjugate(), nfft)[:len(centered)]
    lo, hi = int(60/180*rate/hop), min(len(corr)-1, int(60/75*rate/hop))
    lag = lo + np.argmax(corr[lo:hi+1])
    period = lag * hop / rate
    times = np.array(peaks) * hop / rate
    # Peaks are detected slightly before the transient because of the analysis window.
    times += size / (2 * rate)
    phase = np.angle(np.sum(np.exp(2j*np.pi*times/period))) * period / (2*np.pi)
    grid = np.arange(math.floor((times[0]-phase)/period), math.ceil((times[-1]-phase)/period)+1)*period + phase
    grid = grid[(grid >= 0) & (grid <= len(samples)/rate)]
    return grid.tolist(), 60/period

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--footage', type=Path, default=ROOT/'deliverables/umzug-video/footage')
    p.add_argument('--out', type=Path, default=ROOT/'deliverables/umzug-video/out')
    p.add_argument('--only', choices=['reel','web','gif'])
    p.add_argument('--lang', choices=['de','en','both'], default='both')
    p.add_argument('--config', type=Path, help='JSON object with scene durations in seconds')
    p.add_argument('--preview-without-windows', action='store_true', help='Vorschau ohne Windows-Szene (nur zum Ansehen, nicht veroeffentlichen)')
    p.add_argument('--music', type=Path)
    p.add_argument('--cut-on', choices=['kicks', 'beats', 'bars'], default='kicks')
    p.add_argument('--music-start', type=float, default=0)
    p.add_argument('--duration', type=float, default=20)
    p.add_argument('--every', type=int, default=1)
    a = p.parse_args()
    if not math.isfinite(a.duration) or a.duration <= 0 or not math.isfinite(a.music_start) or a.music_start < 0 or a.every < 1:
        raise ValueError('Ungültiger Musikabschnitt oder --every')
    durations = DEFAULTS.copy()
    order = ['windows', 'installer', 'boot', 'desktop']
    if a.config:
        config = json.loads(a.config.read_text())
        if not isinstance(config, dict) or set(config) - (set(durations) | {'order'}):
            raise ValueError('Konfiguration enthält unbekannte Schlüssel')
        order = config.pop('order', order)
        if not isinstance(order, list) or sorted(order) != sorted(['windows', 'installer', 'boot', 'desktop']):
            raise ValueError('order muss jede Szene genau einmal enthalten')
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
    scenes = {}
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
        frames = visible_frames(frames)
        if not frames: raise ValueError(f'{dirname}: keine sichtbaren Frames')
        scenes[key] = frames
    windows = [(f, n) for f, n in windows if visible_frames([f])]
    if not windows and not a.preview_without_windows:
        raise ValueError('01-windows: keine sichtbaren Bilder')
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='umzug-video-') as tmp:
        tmp = Path(tmp)
        # Windows stills come in different sizes (800x600 ... 1280x800); the concat input needs one size.
        normalized = []
        for i, (still, label) in enumerate(windows):
            with Image.open(still).convert('RGB') as shot:
                canvas = Image.new('RGB', (1280, 800), (22, 27, 37))
                factor = min(1280 / shot.width, 800 / shot.height)
                size = (round(shot.width * factor), round(shot.height * factor))
                canvas.paste(shot.resize(size, Image.LANCZOS), ((1280 - size[0]) // 2, (800 - size[1]) // 2))
                target = tmp / f'windows-{i}.png'
                canvas.save(target)
            normalized.append((target, label))
        windows = normalized
        logo = tmp/'logo.png'
        with Image.open(LOGO).convert('RGBA') as mark:
            background = Image.new('RGBA', mark.size, (22, 27, 37, 255))
            background.alpha_composite(mark)
            background.convert('RGB').save(logo)
        step_text = {i: ['windows', 'installer', 'boot', 'desktop'].index(key)+1 for i, key in enumerate(order, 1)}
        timeline = []
        for step, key in enumerate(order, 1):
            if key == 'windows':
                timeline.extend(([f], durations[key], step, name) for f, name in windows)
            else:
                timeline.append((scenes[key], durations[key], step, ''))
        beat_intervals = None
        if a.music:
            beats, bpm = detect_beats(a.music)
            music_length = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(a.music)]))
            if a.music_start + a.duration > music_length + .001:
                raise ValueError('Musikabschnitt ist länger als die Musikdatei')
            (out/'beats.json').write_text(json.dumps({'bpm': bpm, 'times': beats}, indent=2) + '\n')
            stride = a.every * (4 if a.cut_on == 'bars' else 1)
            cuts = [0.] + [t-a.music_start for t in beats[::stride] if a.music_start + .05 < t < a.music_start+a.duration-.05] + [a.duration]
            # Assign consecutive cuts proportionally, retaining at least two per scene.
            groups = []
            for frames, duration, step, label in timeline:
                if groups and groups[-1][2] == step:
                    groups[-1][0].extend(frames)
                    groups[-1][1] += duration
                else: groups.append([list(frames), duration, step, label])
            end_start = cuts[-2]
            count = len(cuts)-2
            if count < 2*len(groups): raise ValueError('Zu wenige Beats für mindestens zwei Schnitte je Szene')
            weights = np.array([g[1] for g in groups], dtype=float); weights /= weights.sum()
            allocation = np.full(len(groups), 2)
            for _ in range(count - allocation.sum()):
                allocation[np.argmax(weights * count - allocation)] += 1
            beat_intervals = []
            k = 0
            for (frames, _, step, label), ncuts in zip(groups, allocation):
                for j in range(ncuts):
                    # Each cut plays the next contiguous portion, including the final frames.
                    lo = j*len(frames)//ncuts
                    hi = max(lo+1, (j+1)*len(frames)//ncuts)
                    beat_intervals.append((frames[lo:hi] or frames[-1:], cuts[k+1]-cuts[k], step, label))
                    k += 1
            beat_intervals.append(([logo], a.duration-end_start, 5, ''))
        timeline.append(([logo], durations['end'], 5, ''))
        def make_manifest(items):
            manifest = tmp/'frames.ffconcat'
            lines = ['ffconcat version 1.0']
            intervals = []
            cursor = 0
            elapsed = 0.0
            for frames, duration, step, label in items:
                elapsed += duration
                count = max(1, round(elapsed*30) - cursor)
                start = cursor/30
                for j in range(count):
                    frame = frames[min(len(frames)-1, j*len(frames)//count)]
                    path = str(frame.resolve()).replace("'", "'\\''")
                    lines.extend([f"file '{path}'", 'duration 0.033333333333'])
                cursor += count
                intervals.append((start, cursor/30, step, label))
            lines.append(lines[-2])
            manifest.write_text('\n'.join(lines)+'\n')
            return manifest, intervals, cursor/30
        for lang in (['de','en'] if a.lang == 'both' else [a.lang]):
            for kind in (['reel','web'] if a.only is None else (['web'] if a.only == 'gif' else [a.only])):
                portrait = kind == 'reel'
                musical = bool(a.music and portrait)
                manifest, intervals, total = make_manifest(beat_intervals if musical else timeline)
                if musical: total = a.duration
                w,h = (1080,1920) if portrait else (1920,1080)
                fw,fh = (1000,625) if portrait else (1120,700)
                x,y = (40,520) if portrait else (400,180)
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
                for j, line in enumerate(title): draw(line, (160 if portrait else 20)+j*(76 if portrait else 58), 58 if portrait else 50)
                for start,end,step,label in intervals:
                    enable = f'between(t,{start},{end-0.00001})'
                    if step < 5:
                        draw(TEXT[lang][step_text[step]], 1450 if portrait else 940, 52 if portrait else 48, enable=enable)
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
                            px = w//2 + (i-2.5)*64
                            filt.append(f"[v{n}]drawbox=x={int(px)}:y={1530 if portrait else 1020}:w=26:h=26:color={'0xff6a2b' if active else '0x6d7684'}:t=fill:enable='{expr}'[v{n+1}]")
                            n += 1
                for boundary in [end for _, end, step, _ in intervals[:-1] if step == order.index('windows')+1]:
                    fade = min(0.15, durations['windows']/3)
                    # Short dip to dark around the cut. Chained fade filters would blacken everything before the
                    # last fade-in, so the dip is drawn as stepped dark overlays that are only active near the cut.
                    step_len = fade / 3
                    for k, alpha in enumerate((.35, .7, .95, .95, .7, .35)):
                        begin = boundary - fade + k * step_len
                        filt.append(f"[v{n}]drawbox=x=0:y=0:w=iw:h=ih:color=black@{alpha}:t=fill:enable='between(t,{begin:.5f},{begin + step_len - 0.00001:.5f})'[v{n+1}]")
                        n += 1
                target = out/f'umzug-{kind}-{"9x16" if portrait else "16x9"}-{lang}.mp4'
                if a.only == 'gif': target = tmp/f'{lang}.mp4'
                command = ['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(manifest),*(['-ss', str(a.music_start), '-i', str(a.music)] if musical else []),'-filter_complex',';'.join(filt),'-map',f'[v{n}]',*(['-map','1:a:0','-af',f'afade=t=in:st=0:d=0.2,afade=t=out:st={max(0,total-1)}:d=1','-c:a','aac','-b:a','192k'] if musical else ['-an']),'-t',str(total),'-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart','-threads','4',str(target)]
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
