"""Soft gradient wallpapers in WinDoesNot colors. Deterministic (fixed seeds), own work.

Usage: python3 tools/make-wallpapers.py desktop/share/backgrounds/windoesnot
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

W, H = 3840, 2160
w, h = 640, 360  # field resolution, upscaled smoothly
yy, xx = np.mgrid[0:h, 0:w] / h  # y in [0,1], x in [0,1.78]

def hexrgb(c): return np.array([int(c[i:i+2], 16) for i in (1, 3, 5)], float) / 255

def blobs(base, spots):
    """Colour field: base colour plus weighted soft spots (x, y, radius, colour, strength)."""
    img = np.ones((h, w, 3)) * hexrgb(base)
    for x, y, r, col, s in spots:
        wgt = s * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * r * r))
        img = img * (1 - wgt[..., None]) + hexrgb(col) * wgt[..., None]
    return img

def warp(img, seed, amount):
    """Gentle domain warp so the shapes flow instead of being round."""
    rng = np.random.default_rng(seed)
    dx = sum(np.sin(xx * f * 3 + rng.uniform(0, 6) + yy * rng.uniform(-3, 3)) / f for f in (1, 2, 3)) * amount
    dy = sum(np.cos(yy * f * 3 + rng.uniform(0, 6) + xx * rng.uniform(-3, 3)) / f for f in (1, 2, 3)) * amount
    sx = np.clip(((xx + dx) * h).astype(int), 0, w - 1); sy = np.clip(((yy + dy) * h).astype(int), 0, h - 1)
    return img[sy, sx]

def finish(img, name, grain=0.018, blur=18, seed=1):
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(float) / 255
    a += np.random.default_rng(seed).normal(0, grain, (H, W, 1))  # fine film grain, avoids banding
    out = Path(sys.argv[1]) / name
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(out, quality=92, subsampling=0)
    print(out)

# 1 Glut: warm, light, orange flowing shapes (default)
finish(warp(blobs('#f6e7d8', [(0.35, 0.30, 0.22, '#fe6f2d', 1), (0.55, 0.55, 0.25, '#e8402a', .95), (1.25, 0.35, 0.28, '#ffa23a', .95),
                               (1.05, 0.75, 0.22, '#fe6f2d', .9), (0.2, 0.85, 0.2, '#ffb04d', .7), (1.6, 0.9, 0.2, '#f4c08a', .6)]), 3, .06), 'windoesnot-glut.jpg', seed=1)
# 2 Glut dunkel: dark, glowing orange/red
finish(warp(blobs('#121214', [(0.45, 0.62, 0.20, '#fe6f2d', .95), (0.75, 0.45, 0.17, '#c2281f', .9), (1.25, 0.70, 0.22, '#7a1d3a', .85),
                               (1.05, 0.25, 0.15, '#ff8a3d', .6), (0.15, 0.2, 0.25, '#1e1e24', .8)]), 7, .08), 'windoesnot-glut-dunkel.jpg', seed=2)
# 3 Daemmerung: light, peach to soft blue
finish(warp(blobs('#f2ece8', [(0.2, 0.15, 0.3, '#f7b79a', .9), (0.9, 0.2, 0.25, '#f6d2c2', .7), (1.4, 0.75, 0.3, '#6f8fe6', .85),
                               (0.8, 0.85, 0.25, '#a9b8f0', .75), (1.7, 0.2, 0.2, '#fe8a55', .7)]), 11, .05), 'windoesnot-daemmerung.jpg', seed=3)
# 4 Linie: dark petrol into orange along a diagonal band
img = blobs('#0f1a24', [(1.3, 0.3, 0.35, '#e9502e', .9), (1.0, 0.55, 0.25, '#f19a6a', .55), (0.3, 0.8, 0.35, '#163246', .8)])
band = np.exp(-((xx * 0.55 - yy + 0.15) ** 2) / 0.02)
img = img * (1 - band[..., None] * .35) + hexrgb('#ffc39b') * band[..., None] * .35
finish(warp(img, 5, .03), 'windoesnot-linie.jpg', seed=4, blur=14)
