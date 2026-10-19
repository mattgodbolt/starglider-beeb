#!/usr/bin/env python3
"""David Lowe's title tune in Starglider 128 (the Spectrum 128K version): the
AY register writes its own player makes over one pass, and the data it reads.

    .venv/bin/python -I tools/zx_song.py [--snap build/zx128.z80] [OUT.json]

(OUT.json build/zx/song.json if not given.)

The tune and its player are in bank 6 at &C000 (docs/research/zx.md,
"Music"). The menu, idle for 10,000 polls, calls &958B, which pages bank 6
and calls &C000: a loop that reads the keyboard and calls &C071, which
counts 100 calls down and then moves the tune on a tick (&C083). So the
tick's spacing is the loop's speed, with interrupts off. A tick moves three
channels on:

- A (&C088) walks a list of pattern numbers (&C0DB, from the word at &C005;
  &FF goes back to its start). A pattern (the table at &C533) is a byte the
  player skips, then steps of three bytes: a list's address and a count of
  ticks to wait. The list is register and value pairs to &FF, written as
  they are (&C195).
- B (&C0E2) and C (&C1BD) walk lists of their own (&C178 from &C007, &C249
  from &C009): a pattern number, or &C9 and an instrument's number and then
  a pattern number. An instrument (the table at &C585) is register and
  value pairs to &FF, written at once, then volumes to &FF. A pattern is
  notes of three bytes, the tone's period (registers 2-3 for B, 4-5 for C)
  and the ticks it lasts, to &FF. A note writes its period and starts its
  instrument's volumes, one written to register 9 (B) or 10 (C) a tick;
  past the last the volume holds.

This runs the attract screen on the contended simulator, as the menu
reaches it, stops at each tick and logs the AY's writes, until each
channel's list has gone back to its start and then for CHECK ticks more,
which must repeat the pass's first. It times each tick's work, from &C083
to the call's return, and walks the data as the player reads it for the
bytes a transcription of the player would carry. The JSON holds the
clocks, each tick's T-state and its writes (T-state, register, value) for
the pass, the work's mean and most, and the data's addresses.
"""
import argparse
import bisect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zx import Spectrum, run_script  # noqa: E402
from skoolkit.simutils import T  # noqa: E402

CPU_HZ = 3546900                # the 128K's T-states a second
AY_HZ = CPU_HZ / 2              # the AY's clock
TUNE = 0xC000
TICK = 0xC083                   # the tick, its counter run out
TICK_ON = 0xC088                # past the counter's reset, before the tick's work
RETURN = 0xC017                 # the loop, past its call
POINTERS = (0xC0DB, 0xC178, 0xC249)    # each channel's place in its list
STARTS = (0xC005, 0xC007, 0xC009)      # each list's start, less one
PATTERNS = 0xC533
INSTRUMENTS = 0xC585
CODE_END = 0xC27B               # the player's code and variables, &C000 up
CHECK = 2000                    # ticks of the second pass compared with the first
MAX_TICKS = 100000


def word(m, a):
    return m[a] | m[a + 1] << 8


def capture(snap):
    log = []
    spec = Spectrum(snap, portlog=log, cmio=True)
    run_script(spec, "f40", "")
    if spec.run_tstates(30 * 50 * spec.frame, stop=TUNE) != TUNE:
        raise SystemExit("the attract screen's tune never started")
    log.clear()
    m = spec.mem
    ticks, work, wraps, before = [], [], [None, None, None], None
    while len(ticks) < MAX_TICKS:
        if spec.run_tstates(100000, stop=TICK) != TICK:
            raise SystemExit("lost the tune's tick")
        at = spec.sim.registers[T]
        spec.run_tstates(100, stop=TICK_ON)
        ticks.append(spec.sim.registers[T])
        # The pointers as the last tick left them: a fall is a list gone
        # back, which starts the next pass.
        now = [word(m, a) for a in POINTERS]
        if before:
            for c in range(3):
                if now[c] < before[c] and wraps[c] is None:
                    wraps[c] = len(ticks) - 2
        before = now
        spec.run_tstates(100000, stop=RETURN)
        work.append(spec.sim.registers[T] - at)
        if None not in wraps and len(ticks) > max(wraps) + CHECK + 1:
            break
    if None in wraps or len(set(wraps)) != 1:
        raise SystemExit(f"the channels' lists go back at different ticks: {wraps}")
    ay = [(t, r, v) for t, kind, *rest in log if kind == "AY" for r, v in [rest]]
    by_tick = [[] for _ in ticks]
    for t, r, v in ay:
        by_tick[bisect.bisect_right(ticks, t) - 1].append((t, r, v))
    return spec, ticks, by_tick, wraps[0], work[:wraps[0]]


def walk(m):
    """Every address the player reads its data from, by the rules above."""
    read = set()

    def rd(a):
        read.add(a)
        return m[a]

    def pairs(a):
        while rd(a) != 0xFF:
            rd(a + 1)
            a += 2
        return a

    def pattern(n):
        rd(PATTERNS + 2 * n)
        rd(PATTERNS + 2 * n + 1)
        return word(m, PATTERNS + 2 * n)

    a = word(m, STARTS[0]) + 1
    while rd(a) != 0xFF:
        p = pattern(m[a]) + 1
        while True:
            lo, hi = rd(p), rd(p + 1)
            if hi == 0xFF:
                break
            pairs(lo | hi << 8)
            rd(p + 2)
            p += 3
        a += 1
    for c in (1, 2):
        a = word(m, STARTS[c]) + 1
        while rd(a) != 0xFF:
            if m[a] == 0xC9:
                n = rd(a + 1)
                rd(INSTRUMENTS + 2 * n)
                rd(INSTRUMENTS + 2 * n + 1)
                v = pairs(word(m, INSTRUMENTS + 2 * n)) + 1
                while rd(v) != 0xFF:
                    v += 1
                a += 2
                rd(a)
            p = pattern(m[a])
            while rd(p) != 0xFF:
                rd(p + 1)
                rd(p + 2)
                p += 3
            a += 1
    return sorted(read)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="?", default="build/zx/song.json")
    ap.add_argument("--snap", default="build/zx128.z80")
    args = ap.parse_args()
    spec, ticks, by_tick, length, work = capture(args.snap)
    first = [[(r, v) for _, r, v in w] for w in by_tick[:CHECK]]
    again = [[(r, v) for _, r, v in w] for w in by_tick[length:length + CHECK]]
    if first != again:
        raise SystemExit("the second pass doesn't repeat the first")
    data = walk(spec.mem)
    if min(data) < CODE_END:
        raise SystemExit(f"data read inside the player's code, at &{min(data):04X}")
    seconds = (ticks[length] - ticks[0]) / CPU_HZ
    spacing = [b - a for a, b in zip(ticks, ticks[1:length + 1])]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "cpu_hz": CPU_HZ, "ay_hz": AY_HZ, "ticks": ticks[:length + 1], "length": length,
        "writes": [[list(w) for w in ws] for ws in by_tick[:length]],
        "code": [TUNE, CODE_END], "data": data,
        "work_mean": sum(work) / length, "work_max": max(work),
    }) + "\n")
    writes = sum(len(w) for w in by_tick[:length])
    print(f"zx_song: {length} ticks a pass, {seconds:.2f} s, a tick every {seconds / length * 1e3:.3f} ms "
          f"({length / seconds:.2f} Hz; {min(spacing)}-{max(spacing)} T apart); {writes} AY writes; "
          f"a tick's work {sum(work) / length:.0f} T on average, {max(work)} at most, from the tick to "
          f"its return; player &{TUNE:04X}-&{CODE_END - 1:04X} ({CODE_END - TUNE} bytes), data "
          f"{len(data)} bytes in &{min(data):04X}-&{max(data):04X} -> {out}")


if __name__ == "__main__":
    sys.exit(main())
