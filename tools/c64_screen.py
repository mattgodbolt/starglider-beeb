#!/usr/bin/env python3
"""Render a C64 bitmap screen from a RAM image (from c64_unfreeze.py) to PNG.

    c64_screen.py RAM.bin COLOUR.bin OUT.png BITMAP SCREEN [--mc] [--bg N] [--scale N]

BITMAP and SCREEN are hex CPU addresses of the 8000-byte bitmap and the
1000-byte screen matrix. --mc renders multicolour (160x200, double-wide
pixels: %01 = screen high nybble, %10 = screen low nybble, %11 = colour RAM,
%00 = background); without it, hires (320x200: 1 = screen high nybble,
0 = screen low nybble).
"""
import sys
from pathlib import Path

from PIL import Image

# Pepto's PAL palette.
PALETTE = [
    (0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF), (0x68, 0x37, 0x2B), (0x70, 0xA4, 0xB2),
    (0x6F, 0x3D, 0x86), (0x58, 0x8D, 0x43), (0x35, 0x28, 0x79), (0xB8, 0xC7, 0x6F),
    (0x6F, 0x4F, 0x25), (0x43, 0x39, 0x00), (0x9A, 0x67, 0x59), (0x44, 0x44, 0x44),
    (0x6C, 0x6C, 0x6C), (0x9A, 0xD2, 0x84), (0x6C, 0x5E, 0xB5), (0x95, 0x95, 0x95),
]


def render(ram, colour, bitmap, screen, mc, bg):
    img = Image.new("RGB", (320, 200))
    px = img.load()
    for cy in range(25):
        for cx in range(40):
            cell = cy * 40 + cx
            sc = ram[screen + cell]
            cr = colour[cell] & 15
            for row in range(8):
                b = ram[bitmap + cell * 8 + row]
                y = cy * 8 + row
                if mc:
                    for p in range(4):
                        v = (b >> (6 - 2 * p)) & 3
                        c = (bg, sc >> 4, sc & 15, cr)[v]
                        px[cx * 8 + 2 * p, y] = px[cx * 8 + 2 * p + 1, y] = PALETTE[c]
                else:
                    for p in range(8):
                        c = sc >> 4 if b & (0x80 >> p) else sc & 15
                        px[cx * 8 + p, y] = PALETTE[c]
    return img


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = sys.argv[1:]
    ram = Path(args[0]).read_bytes()
    colour = Path(args[1]).read_bytes()
    bitmap = int(args[3].lstrip("&$"), 16)
    screen = int(args[4].lstrip("&$"), 16)
    mc = "--mc" in opts
    bg = int(opts[opts.index("--bg") + 1]) if "--bg" in opts else 0
    scale = int(opts[opts.index("--scale") + 1]) if "--scale" in opts else 2
    img = render(ram, colour, bitmap, screen, mc, bg)
    img = img.resize((320 * scale, 200 * scale), Image.NEAREST)
    img.save(args[2])


if __name__ == "__main__":
    main()
