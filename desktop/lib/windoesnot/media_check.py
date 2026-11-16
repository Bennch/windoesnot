#!/usr/bin/env python3
"""Report locally advertised demuxers and decoders; never opens media or the network."""
import json
import re
import subprocess

CODECS = {'H.264': ('h264', ('avdec_h264', 'openh264dec')), 'H.265': ('hevc', ('avdec_h265', 'libde265dec')), 'AAC': ('aac', ('avdec_aac', 'faad')), 'MP3': ('mp3', ('avdec_mp3', 'mpg123audiodec', 'mad')), 'FLAC': ('flac', ('flacdec', 'avdec_flac')), 'AV1': ('av1', ('av1dec', 'dav1ddec', 'avdec_av1')), 'VP8': ('vp8', ('vp8dec', 'avdec_vp8')), 'VP9': ('vp9', ('vp9dec', 'avdec_vp9')), 'Opus': ('opus', ('opusdec', 'avdec_opus')), 'Vorbis': ('vorbis', ('vorbisdec', 'avdec_vorbis'))}


def parse(formats, codecs, gst):
    # FFmpeg's first codec flag and format flag indicate decoding/demuxing.
    decoded = set(re.findall(r'^\s*D\S{5}\s+(\S+)', codecs, re.M))
    demux = set()
    for names in re.findall(r'^\s*D\s*E?\s+(\S+)', formats, re.M):
        demux.update(names.split(','))
    elements = set(re.findall(r'^\S+:\s+(\S+):', gst, re.M))
    result = {name: {'ffmpeg': codec in decoded, 'gstreamer': any(x in elements for x in names)} for name, (codec, names) in CODECS.items()}
    result['WebM'] = {'ffmpeg': 'matroska' in demux or 'webm' in demux, 'gstreamer': 'matroskademux' in elements}
    return result


def run(args):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=15, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return ''


def main():
    formats = run(['ffprobe', '-v', 'quiet', '-formats']) or run(['ffmpeg', '-hide_banner', '-formats'])
    codecs = run(['ffprobe', '-v', 'quiet', '-codecs']) or run(['ffmpeg', '-hide_banner', '-codecs'])
    print(json.dumps(parse(formats, codecs, run(['gst-inspect-1.0'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
