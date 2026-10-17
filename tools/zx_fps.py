#!/usr/bin/env python3
"""Measure Starglider 128's frame rate, pass by pass, on the Spectrum original.

    .venv/bin/python tools/zx_fps.py SNAP [--pre STEPS] [--during STEPS] [--frames N] [--cmio] [--log FILE] [--48]

Runs SNAP (after the zx.py steps in --pre) through the zx.py steps in
--during, or for N frames, and for every pass of the main loop (&AD67, which
ends by waiting at &94C4 for the interrupt that copies the view to the
screen at &91F7) records: the frames from one copy to the next (always a
whole number, as the copy runs from the frame interrupt), the objects drawn
(calls of &D3AC) and the lines drawn (calls of &8D85). Prints frames per
pass against objects drawn. The addresses are the 128K tape's (v.11/86);
--48 uses the 48K tape's (docs/research/zx.md).
"""
import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zx import Spectrum, run_script  # noqa: E402
from zx_prof import Profiler  # noqa: E402

# (main loop top, buffer-to-screen copy run by the frame interrupt,
# object drawer, line drawer)
ADDRS = {128: (0xAD67, 0x91F7, 0xD3AC, 0x8D85),
         48: (0xB33C, 0xA3E5, 0xBE96, 0x9F89)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snap")
    ap.add_argument("--pre", default="")
    ap.add_argument("--during", help="zx.py steps to run while measuring, in place of --frames")
    ap.add_argument("--frames", type=int, default=500)
    ap.add_argument("--cmio", action="store_true", help="simulate memory and I/O contention")
    ap.add_argument("--log", help="write one line per pass (frames objects lines) to FILE")
    ap.add_argument("--48", dest="is48", action="store_true", help="the 48K tape's addresses")
    args = ap.parse_args()
    MAIN_LOOP, COPY, DRAW_OBJECT, DRAW_LINE = ADDRS[48 if args.is48 else 128]

    spec = Spectrum(args.snap, cmio=args.cmio)
    if args.pre:
        run_script(spec, args.pre, "shots/zx_")
    sites = [(None, a) for a in (MAIN_LOOP, COPY, DRAW_OBJECT, DRAW_LINE)]
    prof = Profiler(spec, sites)
    if args.during:
        spec.run_tstates = prof.run
        run_script(spec, args.during, "shots/zx_")
    else:
        prof.run(args.frames * spec.frame)

    loops = prof.passes[(None, MAIN_LOOP)]
    copies = prof.passes[(None, COPY)]
    objs = prof.passes[(None, DRAW_OBJECT)]
    lines = prof.passes[(None, DRAW_LINE)]
    rows = []
    # A pass runs from one main-loop top to the next; it is charged the
    # frames from the copy inside it to the copy inside the next pass.
    for a, b in zip(loops, loops[1:]):
        c = [t for t in copies if a <= t < b]
        if len(c) != 1:
            continue
        nxt = [t for t in copies if t >= b]
        if not nxt:
            break
        frames = round((nxt[0] - c[0]) / spec.frame)
        n_obj = sum(1 for t in objs if a <= t < b)
        n_line = sum(1 for t in lines if a <= t < b)
        rows.append((frames, n_obj, n_line))
    if args.log:
        with open(args.log, "w") as f:
            for r in rows:
                f.write("%d %d %d\n" % r)
    by_obj = collections.defaultdict(list)
    for fr, o, ln in rows:
        by_obj[o].append((fr, ln))
    total = sum(r[0] for r in rows)
    print(f"{len(rows)} passes, {total} frames: {total / max(len(rows), 1):.2f} frames a pass, "
          f"{50 * len(rows) / max(total, 1):.2f} passes a second")
    hist = collections.Counter(r[0] for r in rows)
    print("frames a pass:", ", ".join(f"{k}: {v}" for k, v in sorted(hist.items())))
    print("objects drawn  passes  frames/pass (min mean max)  lines/pass")
    for o in sorted(by_obj):
        fr = [x[0] for x in by_obj[o]]
        ln = [x[1] for x in by_obj[o]]
        print(f"  {o:3d}  {len(fr):6d}   {min(fr):3d} {sum(fr) / len(fr):5.2f} {max(fr):3d}"
              f"   {sum(ln) / len(ln):6.1f}")


if __name__ == "__main__":
    sys.exit(main())
