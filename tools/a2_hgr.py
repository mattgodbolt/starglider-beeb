#!/usr/bin/env python3
"""Render an Apple II hi-res page from a memory image to PNG.

    a2_hgr.py MEM.bin OUT.png [--page 2000] [--mono] [--scale N]

MEM.bin is a 64K image (a2_image.py's main.bin). Each line is 40 bytes at
&2000 + (y & 7) * &400 + ((y >> 3) & 7) * &80 + (y >> 6) * &28 (from PAGE);
bits 0-6 are seven pixels, low bit leftmost, and bit 7 picks the colour
group. The colour rendering is the usual approximation of NTSC artefact
colour: a lone lit pixel is violet or green (group 0) or blue or orange
(group 1) by column parity, and neighbouring lit pixels are white.
"""
import sys
from pathlib import Path

from PIL import Image


def line_addr(page, y):
    return page + (y & 7) * 0x400 + ((y >> 3) & 7) * 0x80 + (y >> 6) * 0x28


def render(mem, page=0x2000, mono=False):
    img = Image.new("RGB", (280, 192))
    px = img.load()
    for y in range(192):
        a = line_addr(page, y)
        bits, groups = [], []
        for b in mem[a:a + 40]:
            for i in range(7):
                bits.append((b >> i) & 1)
                groups.append(b >> 7)
        for x in range(280):
            if not bits[x]:
                c = (0, 0, 0)
            elif mono or (x > 0 and bits[x - 1]) or (x < 279 and bits[x + 1]):
                c = (255, 255, 255)
            elif groups[x]:
                c = (255, 106, 0) if x & 1 else (20, 150, 255)
            else:
                c = (20, 245, 60) if x & 1 else (200, 60, 255)
            px[x, y] = c
    return img


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = sys.argv[1:]
    mem = Path(args[0]).read_bytes()
    page = int(opts[opts.index("--page") + 1].lstrip("&$"), 16) if "--page" in opts else 0x2000
    scale = int(opts[opts.index("--scale") + 1]) if "--scale" in opts else 2
    img = render(mem, page, "--mono" in opts)
    img.resize((280 * scale, 192 * scale), Image.NEAREST).save(args[1])


if __name__ == "__main__":
    main()
