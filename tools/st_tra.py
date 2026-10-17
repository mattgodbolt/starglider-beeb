#!/usr/bin/env python3
"""Render Starglider's .TRA pictures (TITLE.TRA, RESULT.TRA) to PNG.

    st_tra.py FILE.TRA OUT.png [--scale N]
    st_tra.py --raw FILE OUT.png [--palette FILE.TRA]   a 32000-byte ST
                                    low-res screen dump (four interleaved
                                    bitplanes), e.g. the crack's FIL1-8

The format, from the game's loader (&32EC) and unpacker (&AACA): 32144
bytes; a 144-byte header, then 320 x 200 pixels as 4-bit chunky values,
two to a byte with the left pixel in the high nibble, 160 bytes a line.
In the header, +&00 is a 16-byte colour map the monochrome path uses and
+&14 the palette, 16 STF words (3 bits a gun). The game converts the
chunky pixels to four bitplanes at load time.
"""
import argparse
import struct
from pathlib import Path

from PIL import Image


def st_rgb(w):
    return tuple(((w >> s) & 7) * 255 // 7 for s in (8, 4, 0))


def tra_palette(data):
    return [st_rgb(w) for w in struct.unpack_from(">16H", data, 0x14)]


def tra_image(data):
    pal = tra_palette(data)
    img = Image.new("RGB", (320, 200))
    px = img.load()
    pix = data[0x90:0x90 + 32000]
    for y in range(200):
        for x in range(0, 320, 2):
            b = pix[y * 160 + x // 2]
            px[x, y] = pal[b >> 4]
            px[x + 1, y] = pal[b & 15]
    return img


def raw_image(data, pal):
    img = Image.new("RGB", (320, 200))
    px = img.load()
    for y in range(200):
        for g in range(20):
            planes = struct.unpack_from(">4H", data, y * 160 + g * 8)
            for b in range(16):
                c = sum(((planes[p] >> (15 - b)) & 1) << p for p in range(4))
                px[g * 16 + b, y] = pal[c]
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("out")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--palette")
    ap.add_argument("--scale", type=int, default=1)
    args = ap.parse_args()
    data = Path(args.file).read_bytes()
    if args.raw:
        pal = tra_palette(Path(args.palette).read_bytes()) if args.palette else \
            [(v, v, v) for v in (i * 17 for i in range(16))]
        img = raw_image(data, pal)
    else:
        img = tra_image(data)
        print("palette", " ".join(f"{w:03X}" for w in struct.unpack_from(">16H", data, 0x14)))
    if args.scale > 1:
        img = img.resize((320 * args.scale, 200 * args.scale), Image.NEAREST)
    img.save(args.out)


if __name__ == "__main__":
    main()
