#!/usr/bin/env python3
"""Frame rate of CPC Starglider from a tools/cpc_emu.py port log.

    cpc_fps.py PORTS.LOG [FROM [TO]]

The game double-buffers between &8000 and &C000 and shows a finished frame by
writing CRTC R12 (the screen start, &20 or &30) at &22A4, then waits for VSync.
This counts the 50Hz frames between those writes, from frame FROM to frame TO
(default: all), and prints their histogram, mean and the resulting updates per
second. Gaps over 40 frames (menus, pauses) are left out.
"""
import collections
import sys


def flips(path):
    sel = None
    out = []
    with open(path) as f:
        for line in f:
            frame, _scan, _pc, port, value = line.split()
            if port.startswith("bc"):
                sel = int(value, 16)
            elif port.startswith("bd") and sel == 12:
                out.append(int(frame))
    return out


def main():
    path = sys.argv[1]
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 30
    fl = [f for f in flips(path) if lo <= f <= hi]
    gaps = [b - a for a, b in zip(fl, fl[1:]) if b - a <= 40]
    if not gaps:
        sys.exit("no screen flips in that range")
    hist = collections.Counter(gaps)
    mean = sum(gaps) / len(gaps)
    print(f"{len(gaps)} updates, frames per update: mean {mean:.2f}, min {min(gaps)}, max {max(gaps)}; "
          f"{50 / mean:.1f} updates per second")
    print("histogram:", " ".join(f"{k}:{v}" for k, v in sorted(hist.items())))


if __name__ == "__main__":
    main()
