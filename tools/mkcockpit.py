#!/usr/bin/env python3
"""The cockpit (the ST's RESULT.TRA) in MODE 1: each band of rows in four
of the BBC's eight colours, the ST's shades between them ordered-dithered.

    mkcockpit.py TRA OUT.png [--option NAME] [--flight]    a preview, at 2x
        [--lines RUN.json --frame N]                      with a frame's lines
                                                          (tools/scenerun.mjs's)
    mkcockpit.py TRA --screen OUT [--option NAME]         MODE 1's screen bytes,
                                                          the window empty
    mkcockpit.py TRA --options                            list the options

The view's window (x 16-303, y 10-128) is the ST's: in flight it's cleared
every frame, so --flight shows it empty, as play would. Each option is a
list of bands, (first row, colours), the colours BBC logical 0-3 in that
band: a palette split starts each band after the first (decision 3). The
fewer logical colours change at a split, the fewer palette writes it
takes, and a split's writes must fit a horizontal blank.

The screen is MODE 1's, 25 character rows of 640 bytes (src/defs.6502),
two bits a pixel, four pixels a byte, the leftmost in bits 7 and 3.
"""
import argparse
import struct
from pathlib import Path

from PIL import Image

BBC = {"black": (0, 0, 0), "red": (255, 0, 0), "green": (0, 255, 0), "yellow": (255, 255, 0),
       "blue": (0, 0, 255), "magenta": (255, 0, 255), "cyan": (0, 255, 255), "white": (255, 255, 255)}
VIEW = (16, 303, 10, 128)

OPTIONS = {
    # one split, at the view's bottom edge: the frame above in the view's
    # colours, the panel in its own
    "a": [(0, ["black", "red", "cyan", "white"]), (129, ["black", "blue", "cyan", "white"])],
    # (only logical 3 changes at the split, white to blue)
    "b": [(0, ["black", "red", "cyan", "white"]), (129, ["black", "red", "cyan", "blue"])],
    # a split at the view's top edge too, for the strip of numbers
    "c": [(0, ["black", "blue", "cyan", "yellow"]), (10, ["black", "red", "cyan", "white"]),
          (129, ["black", "blue", "cyan", "red"])],
}

BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def st_rgb(w):
    return tuple(((w >> s) & 7) * 255 // 7 for s in (8, 4, 0))


def load(path):
    d = Path(path).read_bytes()
    pal = [st_rgb(w) for w in struct.unpack_from(">16H", d, 0x14)]
    pix = d[0x90:0x90 + 32000]
    return pal, [[(pix[y * 160 + x // 2] >> (0 if x & 1 else 4)) & 15 for x in range(320)] for y in range(200)]


def dist(a, b):
    # weighted for the eye: green most, blue least
    return 3 * (a[0] - b[0]) ** 2 + 4 * (a[1] - b[1]) ** 2 + 2 * (a[2] - b[2]) ** 2


def mix(rgb, colours):
    """The pair of colours (and the share of the second) whose mix comes
    nearest rgb, in sixteenths."""
    best = None
    for i, p in enumerate(colours):
        for j, q in enumerate(colours):
            for t in range(17):
                m = tuple(p[k] + (q[k] - p[k]) * t / 16 for k in range(3))
                e = dist(rgb, m)
                if best is None or e < best[0]:
                    best = (e, i, j, t)
    return best[1:]


def convert(pal, pix, option, flight):
    bands = OPTIONS[option]
    out = [[0] * 320 for _ in range(200)]
    for b, (y0, names) in enumerate(bands):
        y1 = bands[b + 1][0] if b + 1 < len(bands) else 200
        colours = [BBC[n] for n in names]
        mixes = [mix(c, colours) for c in pal]
        for y in range(y0, y1):
            for x in range(320):
                if flight and VIEW[0] <= x <= VIEW[1] and VIEW[2] <= y <= VIEW[3]:
                    continue
                i, j, t = mixes[pix[y][x]]
                out[y][x] = j if BAYER4[y & 3][x & 3] < t else i
    return out


def screen(out):
    data = bytearray(25 * 640)
    for y in range(200):
        for x in range(320):
            c = out[y][x]
            a = (y >> 3) * 640 + (x >> 2) * 8 + (y & 7)
            p = x & 3
            data[a] |= ((c >> 1) & 1) << (7 - p) | (c & 1) << (3 - p)
    return data


# The ST's colours to the view's logical colours, as the disc maps them for
# now (src/main.6502's model_colours): reds, yellows and pinks 1, blues and
# cyans 2, white 3.
LINE_COLOURS = [0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3]


def plot_line(out, x0, y0, x1, y1, c):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        if 0 <= x0 < 320 and 0 <= y0 < 200:
            out[y0][x0] |= c
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def preview(out, option, path, scale=2):
    bands = OPTIONS[option]
    img = Image.new("RGB", (320, 200))
    px = img.load()
    for b, (y0, names) in enumerate(bands):
        y1 = bands[b + 1][0] if b + 1 < len(bands) else 200
        for y in range(y0, y1):
            for x in range(320):
                px[x, y] = BBC[names[out[y][x]]]
    img.resize((320 * scale, 200 * scale), Image.NEAREST).save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tra")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--option", default="b", choices=sorted(OPTIONS))
    ap.add_argument("--flight", action="store_true")
    ap.add_argument("--options", action="store_true")
    ap.add_argument("--screen", metavar="OUT")
    ap.add_argument("--lines", metavar="RUN.json")
    ap.add_argument("--frame", type=int, default=0)
    args = ap.parse_args()
    if args.options:
        for k, bands in OPTIONS.items():
            print(k, "; ".join(f"from row {y0}: {', '.join(n)}" for y0, n in bands))
        return
    pal, pix = load(args.tra)
    if args.screen:
        Path(args.screen).write_bytes(screen(convert(pal, pix, args.option, True)))
    else:
        out = convert(pal, pix, args.option, args.flight or bool(args.lines))
        if args.lines:
            import json
            frame = json.loads(Path(args.lines).read_text())["frames"][args.frame]
            for _, _, x0, y0, x1, y1, colour in frame["lines"]:
                plot_line(out, x0, y0, x1, y1, LINE_COLOURS[colour & 15])
        preview(out, args.option, args.out)


if __name__ == "__main__":
    main()
