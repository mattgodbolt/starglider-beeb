#!/usr/bin/env python3
"""Where CPC Starglider's time goes, from a tools/cpc_emu.py execution profile.

    cpc_profile.py COV

The profile holds, per address, instructions started and microseconds spent
(Caprice32's cycle count / 4, so CPC wait states are included). The rendered
frames are counted as calls of the view clear at &22CD. The address ranges
below are the engine's parts as identified in docs/research/cpc.md; time
outside them is reported as "other".
"""
import struct
import sys
from pathlib import Path

PARTS = [
    ("interrupt handler and VSync work", 0x1627, 0x16D8),
    ("next scanline (HL += &800, wrap)", 0x1D63, 0x1D73),
    ("pixel address, point plot", 0x1D74, 0x1DE4),
    ("line drawer", 0x1DE5, 0x1F99),
    ("keyboard (PPI/PSG reads)", 0x1F9A, 0x2007),
    ("flip: wait for VSync", 0x22B5, 0x22BB),
    ("clear the view (PUSH)", 0x22CD, 0x230D),
    ("view side borders", 0x2375, 0x23F0),
    ("text and digits", 0x2522, 0x25F1),
    ("crosshair", 0x2B28, 0x2BBD),
    ("panel waveforms", 0x33B9, 0x3434),
    ("8x8 and 16x8 multiplies (square tables)", 0x3929, 0x3A09),
    ("perspective divide (log/exp tables)", 0x3A0A, 0x3B2F),
    ("projection, face test", 0x3C18, 0x3DCC),
    ("sin/cos and 2D rotations", 0x3DCD, 0x3F14),
    ("object position rotations", 0x3F15, 0x4016),
    ("shape basis routines", 0x4017, 0x4AAF),
    ("edge lists and clipping", 0x4AB0, 0x4CED),
    ("vertex programs", 0x4CEE, 0x4D86),
    ("object pass, depth sort, draw list", 0x4D87, 0x5284),
    ("ground markers", 0x5677, 0x5865),
    ("object behaviour (table &65A3)", 0x654B, 0x6DCB),
    ("collisions (table &7111)", 0x6DCC, 0x7273),
    ("sound", 0x7274, 0x7357),
]


def main():
    raw = Path(sys.argv[1]).read_bytes()
    count = struct.unpack("<65536I", raw[:262144])
    us = struct.unpack("<65536I", raw[262144:])
    frames = count[0x22CD] or 1
    total = sum(us)
    print(f"{frames} rendered frames, {total / frames / 1000:.1f} ms each "
          f"({total / frames / 19968:.2f} 50Hz frames)")
    seen = 0
    for name, lo, hi in PARTS:
        t = sum(us[lo:hi + 1])
        seen += t
        print(f"  {name:42s} {100 * t / total:5.1f}%  {t / frames / 1000:6.1f} ms/frame")
    print(f"  {'other':42s} {100 * (total - seen) / total:5.1f}%  {(total - seen) / frames / 1000:6.1f} ms/frame")


if __name__ == "__main__":
    main()
