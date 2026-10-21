#!/usr/bin/env python3
"""David Lowe's title tune (decision 5) for src/song.6502: the data the
Spectrum 128K's player reads, as 6502 source, and the conversion's
constants, checked against tools/mksong.py's model of it.

    mksongdata.py CAPTURE.json OUT.6502

CAPTURE.json is tools/zx_song.py's (build/zx/song.json): bank 6's bytes
from &C000, the addresses the player reads, the pass's ticks and writes.
The data is the player's own, walked by its rules (tools/zx_song.py's
walk), in its order, with only the bytes it reads: the three lists, the
pattern and instrument tables (split into low and high bytes, by number,
0 where no list names one), channel A's patterns and the register lists
they name, B's and C's patterns, and the instruments. Each pointer is a
label; every other byte is the Spectrum's. A list's start is its label,
where the player's pointer starts one byte before it, as the Z80's does.

The constants (each asserted here against the model, over every period
the data holds and every tick of two passes):

- SONG_TICK_US: the tick, the pass's mean in microseconds (mksong.py's
  tick_s), which System VIA T1 runs at.
- A period: SONG_K = round(16384 x mksong.py's ratio); the SN's period is
  (P x SONG_K + 8192) >> 14, rounded as round(P x ratio) is; past 10 bits,
  a channel with no timer goes up octaves, each one more bit off with its
  own rounding, as mksong.py's halving gives.
- The envelope: its steps since register 13's write are floor(n x C / E)
  for n ticks (mksong.py's), C = tick_s x the AY's clock / 16; the player
  adds SONG_ENV_STEP (C in SONG_ENV_BITS fractional bits) a tick to what's
  left, a step taken for each E (shifted alike) it holds.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mksong  # noqa: E402
import zx_song  # noqa: E402

TUNE = zx_song.TUNE
ENV_BITS = 8                            # the envelope's fractional bits (24-bit sums on the 6502)
OCTAVES = 3                             # the most a channel without a timer goes up


def word(m, a):
    return m[a] | m[a + 1] << 8


class Data:
    """The bytes the player reads, by address, each with its source line's
    item: a byte, or a pointer's low or high byte (the label it names)."""

    def __init__(self, m):
        self.m = m
        self.item = {}                  # address: ("b", value) | ("lo"/"hi", label)
        self.labels = {}                # address: its labels

    def byte(self, a):
        self.item.setdefault(a, ("b", self.m[a]))
        return self.m[a]

    def pointer(self, lo_at, hi_at, label):
        for a, half in ((lo_at, "lo"), (hi_at, "hi")):
            if self.item.get(a, (half, label)) != (half, label):
                raise SystemExit(f"&{a:04X}, {label}'s {half} byte, is another's too")
            self.item[a] = (half, label)

    def label(self, a, name):
        names = self.labels.setdefault(a, [])
        if name not in names:
            names.append(name)


def walk(m):
    """The player's rules, as zx_song.walk has them, recording each byte as
    a byte or a pointer, and naming what the pointers lead to."""
    d = Data(m)
    pats, insts = {}, {}
    regs = set()                        # register lists (channel A's steps)
    regs_written = set()

    def pairs(a):
        while d.byte(a) != 0xFF:
            regs_written.add(d.byte(a))
            d.byte(a + 1)
            a += 2
        return a

    def pattern(n):
        a = word(m, zx_song.PATTERNS + 2 * n)
        pats[n] = a
        return a

    lists = []
    a = word(m, zx_song.STARTS[0]) + 1
    lists.append(a)
    while d.byte(a) != 0xFF:
        p = pattern(m[a]) + 1
        d.label(p - 1, f"sg_pat_{m[a]}")
        d.byte(p - 1)                   # (the byte the player skips: kept, as it's the label's)
        while True:
            lo, hi = m[p], m[p + 1]
            if hi == 0xFF:
                d.byte(p)
                d.byte(p + 1)
                break
            r = lo | hi << 8
            regs.add(r)
            d.pointer(p, p + 1, f"sg_regs_{r:04X}")
            d.label(r, f"sg_regs_{r:04X}")
            pairs(r)
            d.byte(p + 2)
            p += 3
        a += 1
    periods = {1: set(), 2: set()}
    for c in (1, 2):
        a = word(m, zx_song.STARTS[c]) + 1
        lists.append(a)
        while d.byte(a) != 0xFF:
            if m[a] == 0xC9:
                n = d.byte(a + 1)
                v = word(m, zx_song.INSTRUMENTS + 2 * n)
                insts[n] = v
                d.label(v, f"sg_ins_{n}")
                v = pairs(v) + 1
                while d.byte(v) != 0xFF:
                    v += 1
                a += 2
            p = pattern(d.byte(a))
            d.label(p, f"sg_pat_{m[a]}")
            while d.byte(p) != 0xFF:
                periods[c].add(d.byte(p) | (d.byte(p + 1) & 15) << 8)
                d.byte(p + 2)
                p += 3
            a += 1
    for i, name in enumerate(("sg_list_a", "sg_list_b", "sg_list_c")):
        d.label(lists[i], name)
    a_periods = set()
    for r in regs:
        q, vals = r, {}
        while m[q] != 0xFF:
            vals[m[q]] = m[q + 1]
            q += 2
        if 0 in vals or 1 in vals:
            a_periods.add(vals.get(0, 0) | (vals.get(1, 0) & 15) << 8)
    return d, pats, insts, regs_written, periods, a_periods


def sn_period(p, k, octaves):
    """The 6502's: (P x SONG_K) rounded off 14 bits, or more for octaves."""
    f = max(1, p) * k
    s = 14 + octaves
    return (f + (1 << (s - 1))) >> s


def check_periods(ratio, k, every):
    for p in sorted(every):
        want = round(max(1, p) * ratio)
        if sn_period(p, k, 0) != want:
            raise SystemExit(f"period {p}: the SN's {sn_period(p, k, 0)}, mksong.py's {want}")
        # the octaves, as mksong.py halves a period that has no timer
        q, n = max(1, p), want
        octaves = 0
        while n >= mksong.SN_PERIODS:
            q /= 2
            n = round(q * ratio)
            octaves += 1
        if octaves > OCTAVES or sn_period(p, k, octaves) != n or (octaves and sn_period(p, k, octaves - 1) < mksong.SN_PERIODS):
            raise SystemExit(f"period {p} up {octaves} octaves: the SN's {sn_period(p, k, octaves)}, mksong.py's {n}")


def check_envelope(cap, tick_s, step):
    """The envelope's steps as the player counts them, against mksong.py's
    floor((k - env_at) x tick_s x ay_hz / (16 x E)), at every tick of two
    passes; E changes only where register 13 is written, so the player's
    count needn't start again but there."""
    length = cap["length"]
    reg = [0] * 16
    env_at, q, r, worst = 0, 0, 0, 0
    for k in range(2 * length):
        e_was = reg[11] | reg[12] << 8
        restarted = False
        for _, rr, v in cap["writes"][k % length]:
            reg[rr] = v
            restarted |= rr == 13
        e = max(1, reg[11] | reg[12] << 8)
        if restarted:
            env_at, q, r = k, 0, 0
        else:
            if e != max(1, e_was):
                raise SystemExit(f"tick {k}: the envelope's period changes without register 13")
            r += step
            while r >= e << ENV_BITS:
                r -= e << ENV_BITS
                q += 1
        if e < 256:
            raise SystemExit(f"tick {k}: the envelope's period {e}, which would take the player's count long")
        want = math.floor((k - env_at) * tick_s * cap["ay_hz"] / (16 * e))
        if q != want:
            raise SystemExit(f"tick {k}: the envelope's step {q}, mksong.py's {want}")
        worst = max(worst, r)
    assert worst + step < 1 << 24


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture")
    ap.add_argument("out")
    args = ap.parse_args()
    cap = json.loads(Path(args.capture).read_text())
    m = bytearray(65536)
    m[TUNE:TUNE + len(cap["bank6"])] = bytes(cap["bank6"])
    d, pats, insts, regs_written, periods, a_periods = walk(m)

    # the tables, by number
    for n in pats:
        d.pointer(zx_song.PATTERNS + 2 * n, zx_song.PATTERNS + 2 * n + 1, f"sg_pat_{n}")
    for n in insts:
        d.pointer(zx_song.INSTRUMENTS + 2 * n, zx_song.INSTRUMENTS + 2 * n + 1, f"sg_ins_{n}")
    # the walk is zx_song.py's, plus the patterns' skipped bytes, which
    # carry their labels
    skipped = {word(m, zx_song.PATTERNS + 2 * n) for n in pats} - set(cap["data"])
    if set(d.item) - skipped != set(cap["data"]):
        raise SystemExit("the walk isn't zx_song.py's")
    if max(regs_written) > 13:
        raise SystemExit(f"the tune writes AY register {max(regs_written)}")

    length = cap["length"]
    tick_s = (cap["ticks"][length] - cap["ticks"][0]) / cap["cpu_hz"] / length
    ratio = mksong.SN_HZ * 16 / cap["ay_hz"]
    k = round(16384 * ratio)
    check_periods(ratio, k, periods[1] | periods[2] | a_periods)
    if any(round(max(1, p) * ratio) >= mksong.SN_PERIODS for p in periods[1]):
        raise SystemExit("channel B goes below the SN's lowest note: it has no timer")
    step = round(tick_s * cap["ay_hz"] / 16 * (1 << ENV_BITS))
    check_envelope(cap, tick_s, step)

    L = ["\\ Generated by tools/mksongdata.py from the Spectrum 128K's bank 6 (David",
         "\\ Lowe's title tune): do not edit.", ""]
    L.append(f"SONG_TICK_US = {round(tick_s * 1e6)}        ; the tick, the pass's mean")
    L.append(f"SONG_K = {k}             ; a period's: the SN's is (P x SONG_K) >> 14, rounded")
    L.append(f"SONG_OCTAVES = {OCTAVES}           ; the most a low note with no timer goes up")
    L.append(f"SONG_ENV_BITS = {ENV_BITS}")
    L.append(f"SONG_ENV_STEP = {step}     ; the envelope's E a tick, in SONG_ENV_BITS fractional bits")
    L.append(f"SONG_TICKS = {length}         ; a pass")
    L.append(f"SONG_BASS_US = {mksong.BASS_US}           ; a bass half-cycle's microseconds a unit of the SN's period")
    L.append(f"SONG_NOISE_SLOW = {mksong.NOISE_SLOW}       ; an AY noise period past this takes the SN's slower rate")
    L.append(f"SONG_NOISE_WHITE = {mksong.NOISE_WHITE}       ; the SN's white noise")
    L.append("\\ the AY's volumes as the SN's attenuations (ym2sn.py's, nm's decision 16)")
    L.append(".sg_volume")
    L.append("    EQUB " + ", ".join(str(v) for v in mksong.VOLUME))
    L.append("")
    tables = [("sg_pat", pats), ("sg_ins", insts)]
    for name, used in tables:
        n = max(used) + 1
        for half, f in (("lo", "LO"), ("hi", "HI")):
            L.append(f".{name}_{half}")
            L.append("    EQUB " + ", ".join(f"{f}({name}_{i})" if i in used else "0" for i in range(n)))
    L.append("")
    # the rest in the Spectrum's order, past the tables' entries (where
    # one isn't a table's, its bytes are something else's: list C's last
    # two are pattern 0's, which no list names)
    table = {zx_song.PATTERNS + 2 * n + i for n in pats for i in (0, 1)} | \
            {zx_song.INSTRUMENTS + 2 * n + i for n in insts for i in (0, 1)}
    run = []

    def flush():
        if run:
            L.append("    EQUB " + ", ".join(run))
            run.clear()

    for a in sorted(set(d.item) - table):
        if a in d.labels:
            flush()
            for name in d.labels[a]:
                L.append(f".{name}             ; (&{a:04X})")
        kind, v = d.item[a]
        if kind == "b":
            run.append(f"&{v:02X}")
        elif kind == "lo":
            run.append(f"LO({v})")
        else:
            run.append(f"HI({v})")
        if len(run) == 16 or a + 1 not in d.item:
            flush()
    flush()
    Path(args.out).write_text("\n".join(L) + "\n")
    size = len(set(d.item) - table) + sum(2 * (max(u) + 1) for _, u in tables)
    print(f"mksongdata: {size} bytes of the tune's data ({len(cap['data'])} read by the Z80's player); "
          f"tick {round(tick_s * 1e6)}us, SONG_K {k}, envelope step {step}")


if __name__ == "__main__":
    main()
