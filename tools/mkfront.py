#!/usr/bin/env python3
"""The front end's data (src/front.6502), from the ST's STAR.PRG and its
TITLE.TRA: the title picture, packed; the colour font; the texts of the
credits, the K screen, the pilot rating, the high scores and the end
screen; the BBC's keys as the ST's; and the high-score table as the program
loads, for the start (src/start.6502) to put in ANDY.

    mkfront.py PRG TRA OUT.6502 INIT.6502 OUT.json [--title NAME]   the data
    mkfront.py PRG TRA --options DIR        a preview of each title option, at 2x

OUT.json holds the same for tools/frontcheck.mjs: the font, the texts, the
ratings, the high scores, the boxes, the keys and the title's screen.

docs/research/st-logic.md, "The front end", says what the ST does with
them. The texts are the ST's bytes as its text printer (&012EC) takes
them: CR, LF, a colour as &80 + the colour, the characters, 0 at the end.

The title is TITLE.TRA in MODE 1 (tools/mkcockpit.py's conversion: each ST
colour the mix of two of the BBC's four nearest it, ordered-dithered),
packed by pack() below, which src/front.6502's unpack reads: bits, taken
from the top of a byte the stream holds when the last is used up, and
bytes, in the order the unpacker wants them. A 0 bit is a run of bytes
copied as they are (its length, then the bytes); a 1 a match (its offset
less one, in 256s plus one, then its low byte, then its length less one),
copied from what's already unpacked. A number is Elias-gamma interlaced:
from 1, each 0 bit is followed by a bit to shift in, and a 1 ends it. The
picture ends at the screen's end, &8000.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mkcockpit  # noqa: E402
import st_prg  # noqa: E402

FONT = 0x16D88                          # the colour font, 8 bytes a glyph from &20
FONT_FIRST, FONT_LAST = 0x20, 0x7F

# The texts, by address, NUL-ended unless a length is given.
TEXTS = [
    ("credits", 0x03BA8, None),         # sub_03B82
    ("k_title", 0x02380, None),         # define_keys &022BE
    ("k_dive", 0x02460, None),          # &022C6: $2DA
    ("k_climb", 0x02480, None),         # &022DA: $2DB
    ("k_left", 0x024A0, None),          # &022EE: $2D8
    ("k_right", 0x024B8, None),         # &02302: $2D9
    ("k_accel", 0x024D0, None),         # &02316: $2DC
    ("k_brake", 0x024E8, None),         # &0232A: $2DD
    ("k_thanks", 0x023EC, None),        # &0233E
    ("k_echo", 0x02501, None),          # key_echo's string after its first byte, the key
    ("r_title", 0x08AC0, None),         # sub_08A0A
    ("r_shots", 0x08AE6, 0x22),         # each number at +&22 (sub_08C90)
    ("r_hits", 0x08B14, 0x22),
    ("r_docks", 0x08B42, 0x22),
    ("r_taken", 0x08B70, 0x22),
    ("r_newline", 0x08B9E, None),
    ("r_accuracy", 0x08BA2, 0x22),
    ("r_rating", 0x08BD0, None),
    ("h_congrats", 0x01686, None),      # sub_00E9E
    ("h_scores", 0x01A14, None),        # sub_00FB2
    ("h_row", 0x01A3A, None),
    ("h_gap", 0x01A48, None),
]
RATINGS = 0x08C50                       # 12 pointers to the ratings' names
TABLE_SCORES = 0x01792                  # 10 BCD longs, the best first
TABLE_NAMES = 0x01536                   # 10 names of 16 bytes
NAME_MAX = 8                            # the most the entry takes (&0105A)
BLOCKS = 0x07754                        # the end screen's boxes (sub_07738)
GREYS = 0x0765A                         # 8 words: its greys
RAINBOW = 0x0766A                       # 16 words: its rainbow

# The title's options: MODE 1's four colours, dithered or not.
TITLE_OPTIONS = {
    "a": (["black", "red", "blue", "white"], True),
    "b": (["black", "red", "blue", "yellow"], True),
    "c": (["black", "red", "cyan", "white"], True),
    "a_plain": (["black", "red", "blue", "white"], False),
}

# The BBC's keys (internal numbers, 16 * row + column; the Master's keypad
# columns 10-12) as the ST's: the same key where the ST has it, by its
# legend, or else its place; keys the ST lacks take scancodes no ST key
# sends. Decision 28's three are COPY, DELETE and the keypad's RETURN.
BBC_ST = {
    0x70: 0x01, 0x30: 0x02, 0x31: 0x03, 0x11: 0x04, 0x12: 0x05, 0x13: 0x06, 0x34: 0x07,
    0x24: 0x08, 0x15: 0x09, 0x26: 0x0A, 0x27: 0x0B, 0x17: 0x0C, 0x18: 0x0D,
    0x59: 0x0E, 0x60: 0x0F,
    0x10: 0x10, 0x21: 0x11, 0x22: 0x12, 0x33: 0x13, 0x23: 0x14, 0x44: 0x15, 0x35: 0x16,
    0x25: 0x17, 0x36: 0x18, 0x37: 0x19, 0x47: 0x1A, 0x38: 0x1B, 0x49: 0x1C, 0x01: 0x1D,
    0x41: 0x1E, 0x51: 0x1F, 0x32: 0x20, 0x43: 0x21, 0x53: 0x22, 0x54: 0x23, 0x45: 0x24,
    0x46: 0x25, 0x56: 0x26, 0x57: 0x27, 0x48: 0x28, 0x58: 0x29, 0x00: 0x2A, 0x78: 0x2B,
    0x61: 0x2C, 0x42: 0x2D, 0x52: 0x2E, 0x63: 0x2F, 0x64: 0x30, 0x55: 0x31, 0x65: 0x32,
    0x66: 0x33, 0x67: 0x34, 0x68: 0x35, 0x50: 0x38, 0x62: 0x39, 0x40: 0x3A,
    0x71: 0x3B, 0x72: 0x3C, 0x73: 0x3D, 0x14: 0x3E, 0x74: 0x3F, 0x75: 0x40, 0x16: 0x41,
    0x76: 0x42, 0x77: 0x43, 0x20: 0x44,
    0x39: 0x48, 0x3B: 0x4A, 0x19: 0x4B, 0x79: 0x4D, 0x3A: 0x4E, 0x29: 0x50,
    0x69: 0x52, 0x4B: 0x53,
    0x4A: 0x65, 0x5B: 0x66, 0x1B: 0x67, 0x2A: 0x68, 0x2B: 0x69, 0x7A: 0x6A, 0x7B: 0x6B,
    0x1A: 0x6C, 0x6B: 0x6D, 0x7C: 0x6E, 0x6C: 0x6F, 0x6A: 0x70, 0x4C: 0x71, 0x3C: 0x72,
    # the BBC's own: _ (beside [), the keypad's # and comma
    0x28: 0x37, 0x5A: 0x54, 0x5C: 0x55,
}
# Their legends, where the BBC's differs from the ST's key in its place.
BBC_LEGEND = {0x18: "^", 0x78: "\\", 0x47: "@", 0x38: "[", 0x48: ":", 0x58: "]", 0x28: "_",
              0x5A: "#", 0x5C: ","}
ST_ASCII = 0x015F6                      # the ST's character by scancode - 1

MASKS = [0x00, 0x0F, 0xF0, 0xFF]        # a logical colour's bits in a MODE 1 byte
PHYS = {"black": 0, "red": 1, "green": 2, "yellow": 3, "blue": 4, "magenta": 5, "cyan": 6, "white": 7}


def nearest(rgb, names, allow_black=False):
    """The index in names of the BBC colour nearest an ST colour, as
    tools/mkcockpit.py weighs them; black only if allowed."""
    best = None
    for i, n in enumerate(names):
        if n == "black" and not allow_black:
            continue
        d = mkcockpit.dist(rgb, mkcockpit.BBC[n])
        if best is None or d < best[0]:
            best = (d, i)
    return best[1]


def text_bytes(prg, addr, length):
    out = []
    while length is None or len(out) < length:
        b = prg.u8(addr + len(out))
        if b == 0 and length is None:
            break
        out.append(b)
    return out


def tty_rows(data):
    """The row the ST's text printer ends on, from row 0: it wraps (to an
    address that isn't the screen's) past row 24, which no text may reach."""
    col = row = 0
    for b in data:
        if b == 0x0D:
            col = 0
        elif b == 0x0A:
            row += 1
        elif b < 0x80:
            col += 1
            if col == 40:
                col, row = 0, row + 1
        assert row < 25, "a text runs past the screen's last row"
    return row


def title_screen(tra, option):
    names, dither = TITLE_OPTIONS[option]
    pal, pix = mkcockpit.load(tra)
    colours = [mkcockpit.BBC[n] for n in names]
    mixes = [mkcockpit.mix(c, colours) for c in pal]
    out = [[0] * 320 for _ in range(200)]
    for y in range(200):
        for x in range(320):
            i, j, t = mixes[pix[y][x]]
            if dither:
                out[y][x] = j if mkcockpit.BAYER4[y & 3][x & 3] < t else i
            else:
                out[y][x] = j if t >= 8 else i
    return out


# --- the packer ---

def gamma_bits(n):
    """Elias-gamma interlaced: n >= 1."""
    assert n >= 1
    bits = []
    top = n.bit_length() - 1
    for k in range(top - 1, -1, -1):
        bits += [0, (n >> k) & 1]
    return bits + [1]


def gamma_cost(n):
    return 2 * (n.bit_length() - 1) + 1


MAX_RUN = 256                           # the packer's longest run of bytes (the format's any)
MAX_LEN = 4096                          # and match


def pack(data):
    n = len(data)
    # each place's matches: the longest at each offset seen, from recent
    # places with the same two bytes, and the screen's own repeats (a byte,
    # a cell, a character row)
    chains = {}
    cands = []
    for i in range(n):
        found = {}
        key = bytes(data[i:i + 2])
        offs = [i - j for j in reversed(chains.get(key, [])[-160:])]
        for off in offs + [1, 2, 4, 8, 16, 640]:
            if off > i or off in found:
                continue
            k = 0
            while i + k < n and k < MAX_LEN and data[i + k - off] == data[i + k]:
                k += 1
            if k >= 2:
                found[off] = k
        cands.append(found)
        chains.setdefault(key, []).append(i)
    INF = 1 << 60
    cost = [INF] * (n + 1)
    step = [None] * (n + 1)
    cost[n] = 0
    for i in range(n - 1, -1, -1):
        best, bs = INF, None
        for run in range(1, min(MAX_RUN, n - i) + 1):
            c = 1 + gamma_cost(run) + 8 * run + cost[i + run]
            if c < best:
                best, bs = c, (0, run)
        for off, k in cands[i].items():
            oc = 1 + gamma_cost((off - 1) // 256 + 1) + 8
            for length in range(2, k + 1):
                c = oc + gamma_cost(length - 1) + cost[i + length]
                if c < best:
                    best, bs = c, (off, length)
        cost[i], step[i] = best, bs
    # the stream: bits into the byte the unpacker loads when it needs one
    out = bytearray()
    state = {"at": None, "used": 8}

    def bit(b):
        if state["used"] == 8:
            state["at"] = len(out)
            out.append(0)
            state["used"] = 0
        if b:
            out[state["at"]] |= 0x80 >> state["used"]
        state["used"] += 1

    i = 0
    while i < n:
        off, length = step[i]
        if off == 0:
            bit(0)
            for b in gamma_bits(length):
                bit(b)
            out += data[i:i + length]
        else:
            bit(1)
            for b in gamma_bits((off - 1) // 256 + 1):
                bit(b)
            out.append((off - 1) & 255)
            for b in gamma_bits(length - 1):
                bit(b)
        i += length
    assert unpack(out, n) == bytes(data)
    return bytes(out)


def unpack(stream, n):
    """src/front.6502's unpack, as a check of the packer."""
    out = bytearray()
    s = {"p": 0, "buf": 0x80}

    def getbit():
        s["buf"] <<= 1
        if s["buf"] & 0xFF == 0:
            v = (stream[s["p"]] << 1) | 1
            s["p"] += 1
            s["buf"] = v
        c = s["buf"] >> 8
        s["buf"] &= 0xFF
        return c

    def gamma():
        v = 1
        while not getbit():
            v = (v << 1) | getbit()
        return v

    while len(out) < n:
        if not getbit():
            k = gamma()
            out += stream[s["p"]:s["p"] + k]
            s["p"] += k
        else:
            hi = gamma() - 1
            lo = stream[s["p"]]
            s["p"] += 1
            off = hi * 256 + lo + 1
            k = gamma() + 1
            for _ in range(k):
                out.append(out[-off])
    return bytes(out)


def equb(L, data, per=24):
    for i in range(0, len(data), per):
        L.append("    EQUB " + ", ".join(f"&{b:02X}" for b in data[i:i + per]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("tra")
    ap.add_argument("out", nargs="?")
    ap.add_argument("init", nargs="?")
    ap.add_argument("json", nargs="?")
    ap.add_argument("--title", default="a", choices=sorted(TITLE_OPTIONS))
    ap.add_argument("--options", metavar="DIR")
    args = ap.parse_args()
    if args.options:
        for name, (names, _) in TITLE_OPTIONS.items():
            out = title_screen(args.tra, name)
            mkcockpit.OPTIONS["title"] = [(0, names)]
            mkcockpit.preview(out, "title", Path(args.options) / f"title_{name}.png")
            print(name, len(pack(mkcockpit.screen(out))))
        return
    prg = st_prg.load(args.prg)

    L = ["\\ Generated by tools/mkfront.py from the ST's STAR.PRG and TITLE.TRA: do not",
         "\\ edit.", ""]
    L.append("\\ the colour font (&16D88): 8 rows a glyph, from &20, the leftmost pixel")
    L.append("\\ bit 7")
    L.append("FONT_FIRST = &20")
    L.append(".fe_font")
    equb(L, [prg.u8(FONT + i) for i in range(8 * (FONT_LAST + 1 - FONT_FIRST))])
    L.append("")
    L.append("\\ the texts, as the ST's printer takes them")
    for name, addr, length in TEXTS:
        data = text_bytes(prg, addr, length)
        shown = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in data)
        L.append(f".tx_{name}   ; {shown[:60]!r}")
        equb(L, data + [0])
    # the credits are the one text that starts at the screen's top (after
    # sub_00F80): check they fit, as the others plainly do
    tty_rows(text_bytes(prg, 0x03BA8, None))
    tty_rows(text_bytes(prg, 0x01686, None) + [0x20] * NAME_MAX)
    L.append("")
    L.append("\\ the ratings' names (&08C50), by rating, 0-11")
    ptrs = [prg.u32(RATINGS + 4 * i) for i in range(12)]
    names = {}
    for p in ptrs:
        if p not in names:
            names[p] = f"tx_rating_{len(names)}"
            data = text_bytes(prg, p, None)
            L.append(f".{names[p]}   ; {bytes(data).decode('latin1')!r}")
            equb(L, data + [0])
    L.append(".rating_lo")
    L.append("    EQUB " + ", ".join(f"LO({names[p]})" for p in ptrs))
    L.append(".rating_hi")
    L.append("    EQUB " + ", ".join(f"HI({names[p]})" for p in ptrs))
    L.append("")

    # the keys
    st_ascii = [prg.u8(ST_ASCII + i) for i in range(0x72)]
    bbc_st = [0] * 128
    bbc_char = [0] * 128
    assert len(set(BBC_ST.values())) == len(BBC_ST), "two BBC keys as one ST key"
    for k, s in BBC_ST.items():
        bbc_st[k] = s
        if k in BBC_LEGEND:
            bbc_char[k] = ord(BBC_LEGEND[k])
        elif s <= 0x72:
            c = st_ascii[s - 1]
            bbc_char[k] = c if c < 0x80 else 0
    L.append("\\ the BBC's keys by internal number: the ST's scancode, 0 for none, and the")
    L.append("\\ character the ST's table gives it (its own legend where the BBC's")
    L.append("\\ differs), 0 for none")
    L.append(".bbc_st")
    equb(L, bbc_st, 16)
    L.append(".bbc_char")
    equb(L, bbc_char, 16)
    keys = sorted(BBC_ST)
    L.append("\\ the keys scanned (the links, 2-9, aren't keys)")
    L.append(".bbc_keys")
    equb(L, keys, 16)
    L.append(f"BBC_KEYS = {len(keys)}")
    L.append("")

    # the colours
    names_, _ = TITLE_OPTIONS[args.title]
    pal = mkcockpit.load(args.tra)[0]
    L.append("\\ the ST's colours (D_019F0) in the printer, as MODE 1 bytes: in the title's")
    L.append("\\ palette, as the K screen prints them, the nearest of its four but black (the")
    L.append("\\ others print in white, 15)")
    L.append(".fe_masks")
    L.append("    EQUB " + ", ".join(f"&{MASKS[nearest(c, names_) if i else 0]:02X}" for i, c in enumerate(pal)))
    L.append("")

    # the end screen
    L.append("\\ the end screen's boxes (sub_07738): the byte column, the top line, the")
    L.append("\\ bytes across, the lines, and the fill: its greys (ST colours 1 and 2)")
    L.append("\\ logical 1, its rainbows and reds (3-6) logical 2")
    a = BLOCKS
    boxes = []
    while True:
        off, colour, w, h, more = prg.u16(a), prg.u8(a + 2), prg.u8(a + 3), prg.u8(a + 4), prg.u8(a + 5)
        y, b = divmod(off, 160)
        assert 1 <= colour <= 6
        boxes.append((4 * (b // 8), y, 4 * (w + 1), h + 1, MASKS[1 if colour <= 2 else 2]))
        a += 6
        if more:
            break
    for label, f in (("box_col", 0), ("box_y", 1), ("box_w", 2), ("box_h", 3), ("box_byte", 4)):
        L.append(f".{label}")
        L.append("    EQUB " + ", ".join(str(bx[f]) for bx in boxes))
    L.append(f"BOXES = {len(boxes)}")
    L.append("\\ its greys (&0765A) and its rainbow (&0766A) as the nearest of the BBC's")
    L.append("\\ colours (greys to black or white)")
    greys = [mkcockpit.st_rgb(prg.u16(GREYS + 2 * i)) for i in range(8)]
    rainbow = [mkcockpit.st_rgb(prg.u16(RAINBOW + 2 * i)) for i in range(16)]
    bw = ["black", "white"]
    hues = [n for n in PHYS if n != "black"]
    L.append(".end_grey_phys")
    L.append("    EQUB " + ", ".join(str(PHYS[bw[nearest(c, bw, True)]]) for c in greys))
    L.append(".end_rain_phys")
    L.append("    EQUB " + ", ".join(str(PHYS[hues[nearest(c, hues, True)]]) for c in rainbow))
    L.append("")

    # the title, last (it may run on past world_list_end)
    scr = mkcockpit.screen(title_screen(args.tra, args.title))
    packed = pack(scr)
    L.append(f"\\ the title (option {args.title!r}: {', '.join(names_)}), packed")
    L.append("TITLE_COLOURS = {" + ", ".join(str(PHYS[n]) for n in names_) + "}")
    L.append(f"TITLE_PACKED = {len(packed)}")
    L.append(".title_packed")
    equb(L, packed, 32)
    Path(args.out).write_text("\n".join(L) + "\n")

    # the start's: the high-score table as the program loads
    I = ["\\ Generated by tools/mkfront.py from the ST's STAR.PRG: do not edit.", ""]
    I.append("\\ the high scores as the program loads (&01792, &01536): each score BCD,")
    I.append("\\ least significant byte first, then each name to its last character, ended")
    I.append("\\ by 0, in NAME_MAX + 1 bytes (the entry takes NAME_MAX)")
    I.append(f"ASSERT NAME_MAX = {NAME_MAX}")
    I.append(".hs_init")
    for i in range(10):
        v = prg.u32(TABLE_SCORES + 4 * i)
        I.append("    EQUB " + ", ".join(f"&{(v >> (8 * k)) & 255:02X}" for k in range(4)) + f"  ; {v:08X}")
    for i in range(10):
        raw = bytes(prg.u8(TABLE_NAMES + 16 * i + k) for k in range(16)).split(b"\0")[0].rstrip(b" ")
        assert len(raw) <= NAME_MAX
        I.append("    EQUB " + ", ".join(f"&{b:02X}" for b in list(raw) + [0] * (NAME_MAX + 1 - len(raw)))
                 + f"  ; {raw.decode('latin1')!r}")
    I.append(".hs_init_end")
    Path(args.init).write_text("\n".join(I) + "\n")

    # --- for the harness ---
    js = {
        "font": [prg.u8(FONT + i) for i in range(8 * (FONT_LAST + 1 - FONT_FIRST))],
        "texts": {name: text_bytes(prg, addr, length) for name, addr, length in TEXTS},
        "ratings": [text_bytes(prg, p, None) for p in ptrs],
        "scores": [prg.u32(TABLE_SCORES + 4 * i) for i in range(10)],
        "names": [list(bytes(prg.u8(TABLE_NAMES + 16 * i + k) for k in range(16)).split(b"\0")[0].rstrip(b" "))
                  for i in range(10)],
        "boxes": boxes,
        "masks": [MASKS[nearest(c, names_) if i else 0] for i, c in enumerate(pal)],
        "bbc_st": bbc_st,
        "bbc_char": bbc_char,
        "title_colours": [PHYS[n] for n in names_],
        "title": list(scr),
    }
    Path(args.json).write_text(json.dumps(js))
    print(f"front: title packed {len(scr)} to {len(packed)}")


if __name__ == "__main__":
    main()
