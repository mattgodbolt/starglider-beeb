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


# The missile view's window (the ST's &06B7E): the picture's character rows
# from the view's first to its last (scan lines 8-135), over the window's
# columns (x 16-303), as the screen holds them, a cell of 8 bytes at a time.
# The view's own rows (10-128, and the window's 129-130) are what the ST
# copies; the rest of those character rows are the cockpit's, which the
# screen already shows.
WIN_CHAR_ROWS = range(1, 17)
WIN_COLS = range(VIEW[0] // 4, VIEW[1] // 4 + 1)
# the inner window, where the missile's view is drawn (the ST's $2A0-$2A6:
# x 80-239, y 16-112), by its cells from the window's first
INNER_CELLS = range(80 // 4 - WIN_COLS[0], 239 // 4 + 1 - WIN_COLS[0])
# the inner window's kinds of row: nothing in it, something only in the
# span (the cells the rows with a little in them all have it in), or more
WK_EMPTY, WK_SPAN, WK_FULL = 0, 1, 2


def window(scr, out_src, out_raw):
    """The window's rows as Baron source, unpacked (RAW, for the harness)
    and as the port keeps them: each row's inner window empty, a span, or
    full; a full row's every cell, another's sides and its span's cells.
    The last row's lines from 131 on (the cockpit's, below the window) are
    kept as zeros, as the ST copies the window's rows to 130 alone."""
    rows = []
    for c in WIN_CHAR_ROWS:
        rows.append(bytes(scr[c * 640 + col * 8 + line] for col in WIN_COLS for line in range(8)))
    Path(out_raw).write_bytes(b"".join(rows))
    last = bytearray(rows[-1])
    for i in range(len(last)):
        if i % 8 >= 131 - 8 * WIN_CHAR_ROWS[-1]:
            last[i] = 0
    rows[-1] = bytes(last)

    def cells(row, which):
        return b"".join(row[8 * c:8 * c + 8] for c in which)

    def lit(row):
        return [c for c in INNER_CELLS if any(row[8 * c:8 * c + 8])]

    sparse = [lit(r) for r in rows if lit(r)]
    # the span: the cells of every row with fewer lit than a quarter of the inner window
    few = [s for s in sparse if len(s) < len(INNER_CELLS) // 4]
    span = range(min(min(s) for s in few), max(max(s) for s in few) + 1)
    left = range(0, INNER_CELLS[0])
    right = range(INNER_CELLS[-1] + 1, len(WIN_COLS))
    kinds, data, offsets = [], bytearray(), []
    for r in rows:
        on = lit(r)
        kind = WK_EMPTY if not on else WK_SPAN if set(on) <= set(span) else WK_FULL
        kinds.append(kind)
        offsets.append(len(data))
        if kind == WK_FULL:
            data += r
        else:
            data += cells(r, left) + cells(r, right)
            if kind == WK_SPAN:
                data += cells(r, span)
    lines = ["\\ Generated by tools/mkcockpit.py from the ST's RESULT.TRA: do not edit.",
             "",
             "\\ The missile view's window: the picture's character rows "
             f"{WIN_CHAR_ROWS[0]}-{WIN_CHAR_ROWS[-1]}, each",
             f"\\ {len(WIN_COLS)} cells of 8 bytes as the screen holds them, by the kind of its",
             "\\ inner window (win_kind): a full row's every cell; another's left side, its",
             "\\ right side, then a span's cells. The last row's lines below the window are",
             "\\ zeros.",
             f"WIN_FIRST_ROW = {WIN_CHAR_ROWS[0]}",
             f"WIN_ROWS = {len(rows)}",
             f"WIN_BYTES = {len(rows[0])}",
             f"WIN_CELLS = {len(WIN_COLS)}",
             f"WIN_INNER = {INNER_CELLS[0]}           ; the inner window's first cell ...",
             f"WIN_INNER_CELLS = {len(INNER_CELLS)}     ; ... and its cells",
             f"WIN_SIDE = {len(left)}",
             f"WIN_SPAN = {span[0]}            ; the span's first cell ...",
             f"WIN_SPAN_CELLS = {len(span)}       ; ... and its cells",
             f"WK_EMPTY = {WK_EMPTY}",
             f"WK_SPAN = {WK_SPAN}",
             f"WK_FULL = {WK_FULL}",
             "ASSERT WIN_SIDE = WIN_CELLS - WIN_INNER - WIN_INNER_CELLS",
             "WIN_KINDS = {" + ", ".join(str(k) for k in kinds) + "}",
             ".win_kind",
             "    EQUB WIN_KINDS",
             ".win_row_lo",
             "    EQUB " + ", ".join(f"LO(win_data + {o})" for o in offsets),
             ".win_row_hi",
             "    EQUB " + ", ".join(f"HI(win_data + {o})" for o in offsets),
             ".win_data"]
    for i in range(0, len(data), 32):
        lines.append("    EQUB " + ", ".join(str(v) for v in data[i:i + 32]))
    Path(out_src).write_text("\n".join(lines) + "\n")


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
    ap.add_argument("--window", nargs=2, metavar=("OUT.6502", "RAW"))
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
    elif args.window:
        window(screen(convert(pal, pix, args.option, False)), *args.window)
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
