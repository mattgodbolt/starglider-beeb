#!/usr/bin/env python3
"""Every term of the ground dots' rotation (tools/mkground.py) against the
ST's floor(m d / 16384), for every entry m (-16384 to 16384) and offset d
(-32768 to 32767): the term as the generated code makes it, its share of
its row's constant included. ground_dots (src/logic/worldlogic.6502) takes
each coordinate, two such terms and the ST's own for the ground's column,
to be within DOT_B of the ST's; this checks the term's bound it rests on.

    groundcheck.py [BOUND]      exit 1 if any term is out by more (2)

The products are quarter-square reads: M's high byte by D's high, whole;
the high bytes only of M's high by D's low and M's low by D's high, each
read without the borrow from its low byte (M = 4|m|, D = d + 32768, an M
of 65536 taken as &FFFF with 1 more in the constant).
"""
import sys

import numpy as np


def f(n):
    return (n * n) // 4


def main():
    bound = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    d = np.arange(-32768, 32768, dtype=np.int64)
    D = d + 32768
    Dh, Dl = D >> 8, D & 255
    worst = 0
    for m in range(-16384, 16385):
        if m == 0:
            continue
        M = 4 * abs(m)
        k = -2 * m - (1 if m < 0 else 0)
        if M == 65536:
            M, k = 65535, k + 1
        mh, ml = M >> 8, M & 255
        g = mh * Dh
        q1 = (f(mh + Dl) >> 8) - (f(np.abs(Dl - mh)) >> 8)
        q2 = (f(ml + Dh) >> 8) - (f(np.abs(Dh - ml)) >> 8)
        G = g + q1 + q2
        got = (-G if m < 0 else G) + k
        want = (m * d * 4) >> 16
        e = int(np.abs(got - want).max())
        worst = max(worst, e)
    print(f"groundcheck: every m and d, each term within {worst} of the ST's")
    sys.exit(0 if worst <= bound else 1)


if __name__ == "__main__":
    main()
