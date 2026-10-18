"""Matrices and offsets for tools/rotcheck.mjs, with the ST's exact rotation
and the model of rotate_approx's (tools/mkrotate.py), bit for bit.

    rotcases.py ROOT OUT.json

The matrices are the ST's from random angles and quarter angles, a steady
turn's (only the heading changing, signs crossing quarters), and made-up
ones with units, zeros and products anywhere, column y's units too. The
offsets include column y's high byte 0 and -1 and the range's ends.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "tools"))
import st_prg  # noqa: E402
import st_render as R  # noqa: E402


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def exact(cam, d):
    return [s16(sum((cam[3 * i + j] * d[j]) >> 14 for j in range(3))) for i in range(3)]


def approx(cam, d):
    """rotate_approx as mkrotate.py makes it: column y's units are products of 255."""
    out = []
    for i in (0, 2):
        acc = 0
        S = 0
        for j in range(3):
            m = cam[3 * i + j]
            if m == 0:
                continue
            if abs(m) == 16384 and j != 1:
                acc += d[j] if m > 0 else -d[j]
                continue
            M8 = 255 if abs(m) == 16384 else min(255, (4 * abs(m) + 128) >> 8)
            Y = ((d[j] & 0xFFFF) >> 8) ^ 0x80
            s = 1 if m > 0 else -1
            acc += s * M8 * Y
            S += s * M8
        acc += -128 * S + ((S + 1) >> 1)
        out.append(s16(acc))
    return out


prg = st_prg.load(str(ROOT / "build/st/STAR.PRG"))
r = R.Renderer(prg)
rng = random.Random(1)
cams = []
# the ST's matrices from random angles, and from angles at the quarters
for _ in range(60):
    p, h, rl = rng.randrange(4096), rng.randrange(4096), rng.randrange(512)
    if rng.random() < 0.3:
        p = rng.choice([0, 1024, 2048, 3072])
    if rng.random() < 0.3:
        rl = rng.choice([0, 128, 256, 384])
    m = r.matrix(*r.angles(p, h, rl))
    cams.append([m[a][b] for a in range(3) for b in range(3)])
# a steady turn: only the heading changing, signs crossing quarters
for h in range(0, 4096, 97):
    m = r.matrix(*r.angles(0, h, 31 * 8 // 8))
    cams.append([m[a][b] for a in range(3) for b in range(3)])
# made-up ones: units, zeros and products anywhere (column y's units too)
choices = [0, 16384, -16384, 1, -1, 31, 32, -32, 33, 16351, 16352, 16353, -16383, 8191, -8192]
for _ in range(80):
    cam = []
    for e in range(9):
        c = rng.random()
        cam.append(rng.choice(choices) if c < 0.6 else rng.randrange(-16383, 16384))
    cams.append(cam)
cases = []
for cam in cams:
    ds = []
    for _ in range(12):
        d = []
        for j in range(3):
            c = rng.random()
            if c < 0.2:
                v = rng.randrange(-256, 256)          # D_hi 0 or -1
            elif c < 0.3:
                v = rng.choice([-32768, 32767, -32767, 32640, 32639, -129, 128, -256, 255, 0])
            else:
                v = rng.randrange(-32768, 32768)
            d.append(v)
        ds.append({"d": d, "exact": exact(cam, d), "approx": approx(cam, d)})
    cases.append({"cam": cam, "ds": ds})
Path(sys.argv[2]).write_text(json.dumps(cases))
print(len(cases), "matrices")
