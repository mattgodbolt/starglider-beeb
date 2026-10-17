#!/usr/bin/env python3
"""Profile the Spectrum original: where the T-states go, bank by bank.

    .venv/bin/python tools/zx_prof.py SNAP [--pre SCRIPT] [--frames N | --during SCRIPT]
        [--pass ADDR ...] [--top N] [--map FILE] [--ranges FILE] [--cmio]

Runs SNAP (after the zx.py steps in --pre, if any) for N frames, or through
the zx.py steps in --during (keys and all), with a callback on every
instruction, so each instruction's cost (the T-states to the next
instruction run; an interrupt handler's own instructions are charged to
themselves, its acceptance to the instruction it interrupted) goes to its
address and to the bank paged at &C000 when it ran. Bare addresses are hex.
Prints:

  - the hottest addresses, as (bank:address, T-states, share);
  - for each --pass ADDR (bank:addr or addr), how often PC reached it and
    the T-states between passes (min, mean, max), in 128K frames;
  - the &7FFD writes made, by value.

--map writes a bank-aware execution map: one 'B:ADDR' line per address
run (B is '-' below &C000). --ranges FILE reads 'name start end' lines
(bank:addr allowed) and totals the T-states inside each range.
"""
import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zx import Spectrum, parse_num, run_script  # noqa: E402
from skoolkit.simutils import PC, T  # noqa: E402


def parse_baddr(s):
    """'6:C000' -> (6, 0xC000); 'C000' or '&C000' -> (None, 0xC000). Bare
    addresses are hex, as the profile prints them."""
    if ":" in s:
        b, a = s.split(":", 1)
        return int(b), parse_num(a if a.startswith(("&", "0x")) else "&" + a)
    return None, parse_num(s if s.startswith(("&", "0x")) else "&" + s)


class Profiler:
    def __init__(self, spec, passes):
        self.spec = spec
        self.cost = collections.Counter()
        self.passes = {p: [] for p in passes}
        self.prev = None  # (key, t0)
        self.bank = spec.mem.o7ffd & 7 if spec.is128 else 0
        self.writes = collections.Counter()
        self.pass_addrs = {a for _, a in passes}
        spec_write = spec.write_port

        def write_port(registers, port, value, offset):
            spec_write(registers, port, value, offset)
            if spec.is128 and port & 0x8002 == 0:
                self.bank = value & 7
                self.writes[value] += 1
        spec.write_port = write_port
        spec.sim.set_tracer(spec)

    def step(self, pc, i, t0):
        b = self.bank if pc >= 0xC000 else None
        if self.prev is not None:
            self.cost[self.prev[0]] += t0 - self.prev[1]
        self.prev = ((b, pc), t0)
        if pc in self.pass_addrs:
            for p in self.passes:
                if p[1] == pc and (p[0] is None or p[0] == b):
                    self.passes[p].append(t0)

    def run(self, tstates, stop=None):
        sim = self.spec.sim
        regs = sim.registers
        end = regs[T] + tstates
        sim.trace(regs[PC], stop, 0, end, 1, None, None, None, lambda pc: "", self.step)
        return regs[PC]


def fmt_key(k):
    b, a = k
    return f"{'-' if b is None else b}:{a:04X}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snap")
    ap.add_argument("--pre", default="", help="zx.py steps to run first, unprofiled")
    ap.add_argument("--frames", type=int, default=50)
    ap.add_argument("--during", help="zx.py steps to run while profiling, in place of --frames")
    ap.add_argument("--pass", dest="passes", action="append", default=[],
                    help="count passes of this address (bank:addr allowed)")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--cmio", action="store_true", help="simulate memory and I/O contention")
    ap.add_argument("--map", help="write the bank-aware execution map to FILE")
    ap.add_argument("--ranges", help="total the T-states in the named ranges in FILE")
    args = ap.parse_args()

    spec = Spectrum(args.snap, cmio=args.cmio)
    if args.pre:
        run_script(spec, args.pre, "shots/zx_")
    passes = [parse_baddr(p) for p in args.passes]
    prof = Profiler(spec, passes)
    t0 = spec.sim.registers[T]
    if args.during:
        spec.run_tstates = prof.run
        run_script(spec, args.during, "shots/zx_")
    else:
        prof.run(args.frames * spec.frame)
    total = spec.sim.registers[T] - t0

    print(f"{total / spec.frame:.1f} frames, {total} T-states")
    print("hottest addresses:")
    for k, c in prof.cost.most_common(args.top):
        print(f"  {fmt_key(k)}  {c:9d}  {100 * c / total:5.1f}%")
    for p, ts in prof.passes.items():
        name = f"{'' if p[0] is None else str(p[0]) + ':'}{p[1]:04X}"
        if len(ts) < 2:
            print(f"pass {name}: {len(ts)} hits")
            continue
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        mean = sum(gaps) / len(gaps)
        f = spec.frame
        print(f"pass {name}: {len(ts)} hits; between passes min {min(gaps) / f:.2f}, "
              f"mean {mean / f:.2f}, max {max(gaps) / f:.2f} frames")
    print("&7FFD writes:", ", ".join(f"{v}x{n}" for v, n in sorted(prof.writes.items())))
    if args.ranges:
        sums = collections.Counter()
        ranges = []
        for line in Path(args.ranges).read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and not line.startswith("#"):
                b, s = parse_baddr(parts[1])
                _, e = parse_baddr(parts[2])
                ranges.append((parts[0], b, s, e))
        for (b, a), c in prof.cost.items():
            for name, rb, s, e in ranges:
                if s <= a <= e and (rb is None or rb == b):
                    sums[name] += c
                    break
            else:
                sums["(other)"] += c
        for name, c in sums.most_common():
            print(f"  {name:20s} {c:10d}  {100 * c / total:5.1f}%")
    if args.map:
        with open(args.map, "w") as f:
            for k in sorted(prof.cost, key=lambda k: (k[1], -1 if k[0] is None else k[0])):
                f.write(fmt_key(k) + "\n")


if __name__ == "__main__":
    sys.exit(main())
