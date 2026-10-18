#!/usr/bin/env python3
"""The panel's data (src/panel.6502), from the ST's STAR.PRG and, for the
few pixels the panel changes without covering, its cockpit picture
(RESULT.TRA, as tools/mkcockpit.py converts it).

    mkpanel.py PRG TRA OUT.6502 OUT.json [--colours NAME]
    mkpanel.py PRG TRA --options        list the colour options

docs/research/st-panel.md says what the ST draws, where and how. This
transcribes its data:

- the font (font_colour &16D88), only the glyphs the panel prints (a char
  the ST draws as another's glyph shares it): the digits first, so a
  digit is its own glyph number, then the space, then the rest. Each glyph
  is 16 bytes, MODE 1's for colour 3: rows 0-7 of its left four pixels,
  then of its right four, as they lie in a character row, so one index
  reaches both;
- the strings the panel prints, as glyph numbers, an ST colour byte as
  &80 + the colour, ended by &FF;
- where each thing is drawn, from the ST's screen offsets, and the tables
  of the cells and texts drawn there (CELLS, TEXTS);
- the scanner's colour by type (&06006);
- the waveforms' 16 frames (&06E2A) as MODE 1 bytes for colour 3, rows 0-7
  of each column in turn (as the glyphs), and each side's frame by step
  (&06D2A, &06D6A);
- the speed column's top rows, which keep the picture's colours with one
  plane changed, as the cockpit dithers them;
- the colours: each ST colour to the band's four, each element's, and
  colour 0's flash to the BBC's eight.

OUT.json holds the same for tools/panelcheck.mjs, with every colour
option's tables, so one build can be drawn in each.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mkcockpit  # noqa: E402
import st_prg  # noqa: E402

FONT = 0x16D88                          # 8 bytes a glyph from char &20
FONT_FIRST, FONT_LAST = 0x20, 0x7A
TYPE_COLOURS = 0x06006                  # a byte by type, 32 of them
BARS = 0x06026                          # 64 words: left group T[i], right T[i + 32]
WAVES = 0x06E2A                         # 16 frames of 64 bytes
WAVE_LEFT, WAVE_RIGHT = 0x06D2A, 0x06D6A    # 16 frame pointers each

# The strings, by address: (name, address, length if not NUL-ended).
STRINGS = [
    ("docking", 0x05536, None),         # world_render &05002
    ("launching", 0x05558, None),       # &0562E
    ("refuelling", 0x0556C, None),      # &051A2
    ("missile_view", 0x05528, None),    # &05284
    ("mine_detected", 0x07BC4, None),   # &07BA0
    ("mine_exploded", 0x07BDC, None),   # &07B94
    ("level", 0x02662, 12),             # level_message &02628, its number after it
    ("manual", 0x00082, None),          # &02644
    ("replenished", 0x025A6, None),     # the post-frame tests &01FD4
    ("press_space", 0x025C8, None),     # &01FF0
    ("or_interrogate", 0x025EA, None),  # &0200C
]
# The game's end in words (&02160), which the start puts in ANDY for the
# panel's printer (src/front_andy.6502), as these glyphs: the energy's
# end ($12C 1) and the shields' (2).
GAME_OVER = [("power", 0x02250), ("shields", 0x0226E)]
# What the heading's letter can be (&05F86-&05F98).
COMPASS = "NESW"

# Where each thing is drawn: the ST's colour screen offset (the second of
# each pair the code chooses between by $2BC), and where the code has it.
PLACES = {
    "score": 0x0010,                    # $128(a6), &00E02
    "kill": 0x0078,                     # $12A(a6), &05068
    "heading": 0x0048,                  # &05FB8; the letter four cells on
    "sector_x": 0x7708,                 # &05EB0
    "sector_z": 0x7710,                 # &05EF8
    "missiles": 0x7780,                 # &05FDE
    "shields": 0x5AB8,                  # &05A50
    "energy": 0x5B18,                   # &05AF6
    "laser": 0x6058,                    # &05BA6
    "scanner": 0x5CC8,                  # &05DB6: its top-left
    "wave_left": 0x6110,                # &0587E
    "wave_right": 0x6148,               # &05900
    "docking": 0x4B10,                  # &05016
    "launching": 0x4B28,                # &05642
    "refuelling": 0x4B20,               # &0519E
    "missile_view": 0x4B30,             # &05280
    "countdown": 0x0F30,                # &052CE
    "mine": 0x4B20,                     # &07BB4
    "level": 0x4B30,                    # &0263C
    "manual": 0x1F58,                   # &02658
    "replenished": 0x3E90,              # &01FE8
    "press_space": 0x44D0,              # &02004
    "or_interrogate": 0x4B10,           # &02020
    "game_over": 0x3E88,                # &02178, on the screen shown
}
# The column gauges: a word's offset and its mask (bit 15 the left pixel).
ALTITUDE = (0x7BD0, 0x03C0)             # &059A8: row 198, upward
SPEED = (0x7C4A, 0x03C0)                # &05A26: plane 1 at row 198, upward
TICKS = (0x6B08, 82 - 80, 206 - 80)     # &05C62: row 171; ticks at 82 + d, 206 + d (&05D70, &05D92)

# The cells of digits and letters, in src/panel.6502's order: (name, cells,
# the first's place, each one's colour).
CELLS = [
    ("score", 8, "score", ["SCORE"] * 8),           # eight BCD digits, the highest first
    ("kill", 4, "kill", ["KILL"] * 4),              # four
    ("heading", 5, "heading", ["HEADING"] * 4 + ["COMPASS"]),   # four, then the letter
    ("sector", 4, "sector_x", ["SECTOR_X"] * 2 + ["SECTOR_Z"] * 2),
    ("missiles", 1, "missiles", ["MISSILES"]),
]
# The texts in the view, in the order src/panel.6502 takes them: the words
# (a label), where, the mode (1: ORed, those the ST prints before its 3D,
# whose lines are ORed over them; 0: opaque, those it prints after) and
# the colour (an element's; None: the colour the ST's last print left).
TEXTS = [
    ("DOCKING", "msg_docking", "docking", 0, 1, "TEXT_15"),         # world_render's start
    ("LAUNCHING", "msg_launching", "launching", 0, 1, "TEXT_15"),   # its lists
    ("MISSILE_VIEW", "msg_missile_view", "missile_view", 0, 0, "TEXT_15"),  # no 3D while it shows
    ("COUNTDOWN", "num_text", "countdown", 0, 1, "TEXT_4"),         # before the missile's 3D
    ("REFUELLING", "msg_refuelling", "refuelling", 0, 0, "TEXT_15"),    # world_render's end
    ("MINE", "msg_mine_detected", "mine", 0, 0, None),              # the handlers'
    ("MINE_EXPLODED", "msg_mine_exploded", "mine", 0, 0, None),
    ("LEVEL", "msg_level", "level", 0, 0, None),                    # level_message's
    ("LEVEL_N", "num_text", "level", "LEVEL_PREFIX", 0, None),      # (its number after its words)
    ("MANUAL", "msg_manual", "manual", 0, 0, None),
    ("DOCKED", "msg_replenished", "replenished", 0, 0, None),       # the post-frame tests'
    ("PRESS_SPACE", "msg_press_space", "press_space", 0, 0, None),
    ("OR_INTERROGATE", "msg_or_interrogate", "or_interrogate", 0, 0, None),
]

BANDS = {b: names for b, names in mkcockpit.OPTIONS["b"]}   # the disc's cockpit (src/engine.6502)
VIEW_BAND, PANEL_BAND = 0, 129
MASKS = [0x00, 0x0F, 0xF0, 0xFF]        # a logical colour's bits in a MODE 1 byte


def st_xy(o):
    """docs/research/st-panel.md's convention: a colour screen offset's
    pixel."""
    y, b = divmod(o, 160)
    return 16 * (b // 8) + (8 if b & 1 else 0), y


def word_pixels(o, mask):
    x, y = st_xy(o & ~7)
    xs = [x + i for i in range(16) if mask & (0x8000 >> i)]
    return xs, y


def palette(tra):
    return mkcockpit.load(tra)[0]


def nearest(rgb, names, allow_black):
    """The band's logical colour nearest an ST colour, as mkcockpit
    weighs colours (black only for black)."""
    best = None
    for i, n in enumerate(names):
        if i == 0 and not allow_black:
            continue
        d = mkcockpit.dist(rgb, mkcockpit.BBC[n])
        if best is None or d < best[0]:
            best = (d, i)
    return best[1]


def band_map(pal, band):
    names = BANDS[band]
    return [0] + [nearest(pal[c], names, False) for c in range(1, 16)]


# The elements and their ST colours (docs/research/st-panel.md); the band
# each is in decides which four it can have.
ELEMENTS = [
    ("score", 3, VIEW_BAND), ("kill", 4, VIEW_BAND), ("heading", 1, VIEW_BAND), ("compass", 2, VIEW_BAND),
    ("bar", 5, PANEL_BAND), ("bar_dim", 10, PANEL_BAND),
    ("alt_low", 1, PANEL_BAND), ("alt_high", 2, PANEL_BAND), ("alt_warn", 6, PANEL_BAND),
    ("speed", 2, PANEL_BAND), ("tick", 1, PANEL_BAND), ("wave", 3, PANEL_BAND),
    ("sector_x", 4, PANEL_BAND), ("sector_z", 3, PANEL_BAND), ("missiles", 4, PANEL_BAND),
    ("player", 15, PANEL_BAND),
    ("text_15", 15, VIEW_BAND), ("text_4", 4, VIEW_BAND), ("text_3", 3, VIEW_BAND),
]
# The options: each ST colour to the nearest of the band's four, with
# overrides by element, or for the scanner by ST colour (in the panel band).
OPTIONS = {
    # nearest, but the low-altitude warning, whose green (2) and cyan (6)
    # both come out cyan, blinks to blue
    "nearest": {"elements": {"alt_warn": 3}, "scanner": {}},
    # the scanner's dots as the view's lines are (src/main.6502's
    # st_colours: 1-5 red, 6-14 cyan, white logical 3, which is blue
    # below the split), and the player white's logical 3 too
    "as_view": {"elements": {"alt_warn": 3, "player": 3},
                "scanner": {c: 1 if c <= 5 else 2 if c <= 14 else 3 for c in range(1, 16)}},
    # nearest, with the dark blues and white blue on the scanner, so
    # three kinds show: warm, light, dark
    "three": {"elements": {"alt_warn": 3, "player": 3},
              "scanner": {15: 3}},
}


def colours(pal, option):
    view, panel = band_map(pal, VIEW_BAND), band_map(pal, PANEL_BAND)
    o = OPTIONS[option]
    scan = list(panel)
    for c, v in o["scanner"].items():
        scan[c] = v
    elements = {}
    for name, c, band in ELEMENTS:
        elements[name] = o["elements"].get(name, (view if band == VIEW_BAND else panel)[c])
    return {"view": view, "panel": panel, "scanner": scan, "elements": elements}


def flash_table(pal_unused=None):
    """Colour 0's flash (docs/research/st-panel.md, section 9) as the
    BBC's physical colour: an ST colour by the top two bits of each
    channel, to the nearest of the eight but black (only black stays
    black)."""
    phys = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
    out = []
    for i in range(64):
        r, g, b = (i >> 4) & 3, (i >> 2) & 3, i & 3
        if r == g == b == 0:
            out.append(0)
            continue
        rgb = tuple(v * 2 * 255 // 7 for v in (r, g, b))
        best = min(range(1, 8), key=lambda k: mkcockpit.dist(rgb, mkcockpit.BBC[phys[k]]))
        out.append(best)
    return out


def glyph_bytes(prg, ch):
    a = FONT + 8 * (ord(ch) - FONT_FIRST)
    rows = [prg.u8(a + r) for r in range(8)]
    spread = lambda n: n | (n << 4)
    return [spread(g >> 4) for g in rows] + [spread(g & 15) for g in rows]


def read_string(prg, addr, length):
    out = []
    while length is None or len(out) < length:
        b = prg.u8(addr + len(out))
        if b == 0 and length is None:
            break
        out.append(b)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("tra")
    ap.add_argument("out", nargs="?")
    ap.add_argument("json", nargs="?")
    ap.add_argument("start", nargs="?", help="the game's end in words, for the start")
    ap.add_argument("--colours", default="as_view", choices=sorted(OPTIONS))
    ap.add_argument("--options", action="store_true")
    args = ap.parse_args()
    prg = st_prg.load(args.prg)
    pal = palette(args.tra)
    if args.options:
        for name in OPTIONS:
            c = colours(pal, name)
            print(name, json.dumps(c))
        return

    # The strings and the glyphs they need: the digits first, then the space.
    strings = {name: read_string(prg, a, n) for name, a, n in STRINGS}
    game_over = {name: read_string(prg, a, None) for name, a in GAME_OVER}
    chars = [chr(c) for c in range(ord("0"), ord("9") + 1)] + [" "] + list(COMPASS)
    for s in list(strings.values()) + list(game_over.values()):
        for b in s:
            if b < 0x80 and chr(b) not in chars:
                assert FONT_FIRST <= b <= FONT_LAST, f"char &{b:02X} isn't in the font"
                chars.append(chr(b))
    # (a char the ST draws as another, as its blank colon, shares its glyph)
    glyph, kept = {}, []
    for ch in chars:
        b = glyph_bytes(prg, ch)
        same = [k for k, c in enumerate(kept) if glyph_bytes(prg, c) == b]
        glyph[ch] = same[0] if same else len(kept)
        if not same:
            kept.append(ch)
    assert all(glyph[str(d)] == d for d in range(10)) and len(kept) < 128

    # The bars' patterns: i + 1 pixels from the left, across two groups.
    for i in range(32):
        n = i + 1
        left = ((0xFFFF << (16 - min(n, 16))) & 0xFFFF)
        right = ((0xFFFF << (16 - max(n - 16, 0))) & 0xFFFF) if n > 16 else 0
        assert prg.u16(BARS + 2 * i) == left and prg.u16(BARS + 64 + 2 * i) == right, f"bar {i}"

    # The waveforms: colour 3 only (planes 0 and 1), as MODE 1 bytes.
    frames = []
    for k in range(16):
        rows = []
        for r in range(8):
            planes = [prg.u16(WAVES + 64 * k + 8 * r + 2 * p) for p in range(4)]
            assert planes[0] == planes[1] and planes[2] == planes[3] == 0, f"wave {k} row {r}"
            bits = planes[0]
            out = []
            for byte in range(4):
                n = (bits >> (12 - 4 * byte)) & 15
                out.append(n | (n << 4))
            rows.append(out)
        frames.append(rows)
    order = {}
    for name, table in (("left", WAVE_LEFT), ("right", WAVE_RIGHT)):
        order[name] = []
        for i in range(16):
            p = prg.u32(table + 4 * i)
            k, r = divmod(p - WAVES, 64)
            assert r == 0 and 0 <= k < 16, f"{name} wave pointer {i}"
            order[name].append(k)

    types = [prg.u8(TYPE_COLOURS + t) for t in range(32)]
    places = {k: st_xy(v) for k, v in PLACES.items()}
    alt_xs, alt_y = word_pixels(*ALTITUDE)
    speed_xs, speed_y = word_pixels(*SPEED)
    tick_x, tick_y = st_xy(TICKS[0])
    assert alt_y == speed_y == 198 and tick_y == 171

    # The speed column's top three rows keep the picture's colour, plane 1
    # changed (&05A2E, &05A3E): row 170 lit (10) only at the top speed, row
    # 169 always cleared, row 168 never lit. Their pixels, as the cockpit
    # dithers those colours.
    pix = mkcockpit.load(args.tra)[1]
    names = BANDS[PANEL_BAND]
    mixes = [mkcockpit.mix(c, [mkcockpit.BBC[n] for n in names]) for c in pal]

    def dithered(x, y, c):
        i, j, t = mixes[c]
        return j if mkcockpit.BAYER4[y & 3][x & 3] < t else i

    def column_bytes(y, colour_of):
        """The two MODE 1 bytes (and masks) of the speed column's row y."""
        out = []
        for col in (speed_xs[0] // 4, speed_xs[-1] // 4):
            value = mask = 0
            for x in speed_xs:
                if x // 4 != col:
                    continue
                p = x & 3
                bits = (0x88 >> p)
                mask |= bits
                value |= bits & MASKS[colour_of(x)]
            out.append((value, mask))
        return out
    notch = {}
    for y, plane_set in ((169, False), (170, True), (170, False)):
        key = f"{y}_{'lit' if plane_set else 'unlit'}"
        notch[key] = column_bytes(y, lambda x: dithered(x, y, (pix[y][x] | 2) if plane_set else (pix[y][x] & ~2)))
    assert all(pix[168][x] & 2 == 0 for x in speed_xs)          # row 168 untouched

    opts = {name: colours(pal, name) for name in OPTIONS}
    chosen = opts[args.colours]
    flash = flash_table()

    # --- the 6502 ---
    L = ["\\ Generated by tools/mkpanel.py from the ST's STAR.PRG: do not edit.", ""]
    L.append(f"PANEL_GLYPHS = {len(kept)}")
    L.append(f"LEVEL_PREFIX = {len(strings['level'])}       ; the cells before LEVEL's number")
    L.append(f"GLYPH_SPACE = {glyph[' ']}")
    for ch in COMPASS:
        L.append(f"GLYPH_{ch} = {glyph[ch]}")
    for k, (x, y) in places.items():
        L.append(f"P_{k.upper()}_X = {x}")
        L.append(f"P_{k.upper()}_Y = {y}")
    assert alt_xs[-1] - alt_xs[0] == 3 and speed_xs[-1] - speed_xs[0] == 3
    L.append(f"P_ALT_X0 = {alt_xs[0]}")
    L.append(f"P_ALT_X1 = {alt_xs[-1]}")
    L.append(f"P_SPEED_X0 = {speed_xs[0]}")
    L.append(f"P_SPEED_X1 = {speed_xs[-1]}")
    L.append(f"P_TICK_X0 = {tick_x + TICKS[1]}")
    L.append(f"P_TICK_X1 = {tick_x + TICKS[2]}")
    L.append(f"P_TICK_Y = {tick_y - 1}")
    L.append("")
    L.append("\\ the glyphs: 16 bytes each (see tools/mkpanel.py)")
    L.append(".panel_font")
    for ch in kept:
        L.append("    EQUB " + ", ".join(f"&{b:02X}" for b in glyph_bytes(prg, ch)) + f"  ; {ch!r}")
    L.append("")
    for name, s in strings.items():
        text = "".join(chr(b) if b < 0x80 else "?" for b in s)
        L.append(f".msg_{name}   ; {text!r}")
        out = [glyph[chr(b)] if b < 0x80 else b for b in s] + [0xFF]
        L.append("    EQUB " + ", ".join(f"&{b:02X}" for b in out))
    L.append("")
    L.append("\\ the game's end in words: its strings' bytes (tools/mkpanel.py's GAME_OVER,")
    L.append("\\ for the start to put in ANDY)")
    for name, s in game_over.items():
        L.append(f"GO_{name.upper()}_BYTES = {len(s) + 1}")
    L.append("")

    def scr(x, y, cells=None):
        col = f"{x // 4}" if cells is None else f"({x // 4} + 2 * {cells})"
        return f"SCREEN + {y // 8} * SCREEN_ROW + {col} * 8 + {y % 8}"

    L.append("\\ the cells: each one's byte (its top line's), the line from which it lies")
    L.append("\\ in the next character row, and its colour (an offset in panel_colours)")
    cells, n = [], 0
    for name, count, place, cols in CELLS:
        L.append(f"CELL_{name.upper()} = {n}")
        x, y = places[place]
        for i in range(count):
            cells.append((x + 8 * i, y, cols[i]))
        n += count
    L.append(f"CELLS = {n}")
    for label, f in (("cell_lo", lambda x, y, c: f"LO({scr(x, y)})"), ("cell_hi", lambda x, y, c: f"HI({scr(x, y)})"),
                     ("cell_split", lambda x, y, c: f"{8 - y % 8}"), ("cell_colour", lambda x, y, c: f"PC_{c} - panel_colours")):
        L.append(f".{label}")
        L.append("    EQUB " + ", ".join(f(*cell) for cell in cells))
    L.append("")
    L.append("\\ the texts in the view: the words, where (as the cells), the mode (1: ORed,")
    L.append("\\ as the ST prints them before its 3D) and the colour (&FF: the current one)")
    for i, t in enumerate(TEXTS):
        L.append(f"TXT_{t[0]} = {i}")
    # (each text's top row, for what must know where the texts lie)
    L.append("TXT_Y = {" + ", ".join(str(places[t[2]][1]) for t in TEXTS) + "}")

    def text_at(t, part):
        x, y = places[t[2]]
        cells_ = t[3] if t[3] else None
        return f"{part}({scr(x, y, cells_)})"
    for label, f in (("txt_str_lo", lambda t: f"LO({t[1]})"), ("txt_str_hi", lambda t: f"HI({t[1]})"),
                     ("txt_lo", lambda t: text_at(t, "LO")), ("txt_hi", lambda t: text_at(t, "HI")),
                     ("txt_split", lambda t: f"{8 - places[t[2]][1] % 8}"), ("txt_mode", lambda t: f"{t[4]}"),
                     ("txt_colour", lambda t: f"PC_{t[5]} - panel_colours" if t[5] else "&FF")):
        L.append(f".{label}")
        L.append("    EQUB " + ", ".join(f(t) for t in TEXTS))
    L.append("")
    L.append("\\ the scanner's colours by type (&06006): ST colours (11's is the beam's)")
    L.append(".scan_type_colour")
    L.append("    EQUB " + ", ".join(f"{c}" for c in types))
    L.append("")
    L.append("\\ the waveforms' frames (&06E2A): rows 0-7 of each of the four columns, and")
    L.append("\\ each side's frame by step")
    L.append(".wave_frames")
    for k, rows in enumerate(frames):
        L.append("    EQUB " + ", ".join(f"&{rows[r][c]:02X}" for c in range(4) for r in range(8)) + f"  ; {k}")
    for name in ("left", "right"):
        L.append(f".wave_{name}")
        L.append("    EQUB " + ", ".join(f"{k}" for k in order[name]))
    L.append("")
    L.append("\\ the speed column's top rows, as the picture's colours with plane 1 changed")
    for key, pairs in notch.items():
        L.append(f"SPEED_{key.upper()}_0 = &{pairs[0][0]:02X}")
        L.append(f"SPEED_{key.upper()}_1 = &{pairs[1][0]:02X}")
    L.append(f"SPEED_MASK0 = &{notch['169_unlit'][0][1]:02X}")
    L.append(f"SPEED_MASK1 = &{notch['169_unlit'][1][1]:02X}")
    L.append("")
    L.append(f"\\ the colours (option {args.colours!r}): each element's MODE 1 mask, then")
    L.append("\\ the scanner's by ST colour (the panel's band), then the view's")
    L.append(".panel_colours")
    for i, (name, _, _) in enumerate(ELEMENTS):
        L.append(f"PC_{name.upper()} = panel_colours + {i}")
        L.append(f"    EQUB &{MASKS[chosen['elements'][name]]:02X}")
    L.append(f"PC_SCAN = panel_colours + {len(ELEMENTS)}")
    L.append("    EQUB " + ", ".join(f"&{MASKS[c]:02X}" for c in chosen["scanner"]))
    L.append(f"PC_VIEW = panel_colours + {len(ELEMENTS) + 16}")
    L.append("    EQUB " + ", ".join(f"&{MASKS[c]:02X}" for c in chosen["view"]))
    L.append("")
    L.append("\\ colour 0's flash: the BBC's physical colour by the top two bits of the ST's")
    L.append("\\ red, green and blue")
    L.append(".flash_colour")
    L.append("    EQUB " + ", ".join(str(c) for c in flash))
    Path(args.out).write_text("\n".join(L) + "\n")

    # --- for the harness ---
    js = {
        "glyphs": chars,
        "font": {ch: [prg.u8(FONT + 8 * (ord(ch) - FONT_FIRST) + r) for r in range(8)] for ch in chars},
        "strings": {k: "".join(chr(b) if b < 0x80 else f"\\x{b:02x}" for b in s) for k, s in strings.items()},
        "places": places,
        "cells": cells,
        "texts": [{"name": t[0], "string": t[1].replace("msg_", ""), "place": t[2], "after": t[3],
                   "or": t[4], "colour": t[5]} for t in TEXTS],
        "level_prefix": len(strings["level"]),
        "altitude_x": alt_xs, "speed_x": speed_xs, "tick_x": [tick_x + TICKS[1], tick_x + TICKS[2]],
        "tick_y": tick_y - 1,
        "types": types,
        "waves": [[[(b >> 4) for b in row] for row in rows] for rows in frames],
        "wave_order": order,
        "notch": {k: [[v, m] for v, m in pairs] for k, pairs in notch.items()},
        "speed_cols": [speed_xs[0] // 4, speed_xs[-1] // 4],
        "masks": MASKS,
        "elements": [e[0] for e in ELEMENTS],
        "options": opts,
        "chosen": args.colours,
        "flash": flash,
        "bands": {str(k): v for k, v in BANDS.items()},
    }
    Path(args.json).write_text(json.dumps(js, indent=1))

    # --- the start's: the game's end in words, as glyphs ---
    if args.start:
        S = ["\\ Generated by tools/mkpanel.py from the ST's STAR.PRG: do not edit.", ""]
        S.append("\\ the game's end in words (&02160), as the panel's glyphs, ended by &FF")
        for name, s in game_over.items():
            S.append(f".go_{name}_init   ; {''.join(chr(b) for b in s)!r}")
            S.append("    EQUB " + ", ".join(f"&{glyph[chr(b)]:02X}" for b in s) + ", &FF")
        Path(args.start).write_text("\n".join(S) + "\n")


if __name__ == "__main__":
    main()
