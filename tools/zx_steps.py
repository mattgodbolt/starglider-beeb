#!/usr/bin/env python3
"""Time each step of Starglider 128's main loop on the Spectrum original.

    .venv/bin/python tools/zx_steps.py SNAP [--pre STEPS] [--frames N] [--cmio]

Runs SNAP for N frames, noting when PC reaches each call site of the main
loop (&AD67-&ADCC in the 128K tape, v.11/86), and prints the mean T-states
a pass from each site to the next: the inclusive cost of each call. A frame
interrupt's work is charged to the step it lands in; the copy and clear of
the view run from the interrupt that ends the wait at &AD85 (&94C4), so they
fall in that step, with the wait itself.
"""
import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zx import Spectrum, run_script  # noqa: E402
from zx_prof import Profiler  # noqa: E402

# Call site -> what the call does (docs/research/zx.md, "The main loop").
SITES = {
    0xAD67: "&DBC3", 0xAD6A: "&94B6 clear the vertex buffer",
    0xAD6D: "&D173 move objects, cull, into view space",
    0xAD70: "&9478", 0xAD73: "&D3F9 horizon", 0xAD76: "&D9B1 ground dots",
    0xAD79: "&A508 draw objects far to near", 0xAD7C: "&A7E1", 0xAD7F: "&A26C",
    0xAD82: "&DBC3", 0xAD85: "&94C4 wait; interrupt copies and clears the view",
    0xAD88: "&DBEA", 0xAD8B: "&AE87", 0xAD8E: "&9B28 panel bars",
    0xAD91: "&A77C", 0xAD94: "&9D02 heading and sector", 0xAD97: "(test &561C)",
    0xAD9E: "&E8DE", 0xADA1: "&E4DA objects", 0xADA4: "(test &5646)",
    0xADAB: "&EBF3", 0xADAE: "&DC0E objects", 0xADB1: "&EA2B", 0xADB4: "&EBAC",
    0xADB7: "(test &5644)", 0xADBE: "&8FE6 read a key", 0xADC1: "(key 5)",
    0xADC6: "&ADCF", 0xADC9: "&ADE7", 0xADCC: "JP &AD67",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snap")
    ap.add_argument("--pre", default="")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--cmio", action="store_true", help="simulate memory and I/O contention")
    args = ap.parse_args()

    spec = Spectrum(args.snap, cmio=args.cmio)
    if args.pre:
        run_script(spec, args.pre, "shots/zx_")
    prof = Profiler(spec, [(None, a) for a in SITES])
    prof.run(args.frames * spec.frame)
    events = sorted((t, a) for (_, a), ts in prof.passes.items() for t in ts)
    cost = collections.Counter()
    for (t0, a0), (t1, _) in zip(events, events[1:]):
        cost[a0] += t1 - t0
    passes = len(prof.passes[(None, 0xAD67)]) or 1
    print(f"{passes} passes in {args.frames} frames: {args.frames / passes:.2f} frames a pass")
    for a, name in SITES.items():
        print(f"  &{a:04X}  {cost[a] / passes:9.0f} T a pass  {name}")


if __name__ == "__main__":
    sys.exit(main())
