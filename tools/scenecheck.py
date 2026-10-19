#!/usr/bin/env python3
"""Compare the port's renderer on captured scenes (tools/scenerun.mjs) with
the ST's (tools/mkscene.py's expectations, from tools/st_render.py).

    scenecheck.py SCENES.json RUN.json [--show N] [--tolerance PX]

The lists and the camera-space positions are the game's logic: they must
match exactly, but for the objects the port rotated approximately
(decision 11), whose x' and z' must be within the approximation's bound
(it makes no y': decision 21) and which must be neither drawn nor near
the player in x and z on the ST, and those it found far off (decision
47), whose sentinel the ST must have where nothing reads their x' and z':
neither drawn nor near, nor in the scanner's square. Lines are compared
by object and edge:
an edge drawn by one
and not the other is a culling difference (decision 9 moves the test into
object space); an edge both draw must lie within --tolerance pixels of the
ST's: each end of either line within that distance of the other line,
rounded. (A clipped end can slide along the window's edge further than
its line moves: a nearly level line crossing the window's bottom edge can
end several pixels away for a pixel's difference in height.)
Prints a summary and the cycles each part took, and exits non-zero on a
difference the rules don't allow.
"""
import argparse
import collections
import json
import math
import statistics
import sys
from pathlib import Path


def to_segment(p, a, b):
    """The distance from point p to the segment a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    t = 0 if not n else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def apart(p, q):
    """How far apart two lines are: the furthest end of either from the other."""
    a, b, c, d = p[:2], p[2:4], q[:2], q[2:4]
    return max(to_segment(a, c, d), to_segment(b, c, d), to_segment(c, a, b), to_segment(d, a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes")
    ap.add_argument("run")
    ap.add_argument("--show", type=int, default=5)
    ap.add_argument("--tolerance", type=int, default=0)
    args = ap.parse_args()
    scenes = json.loads(Path(args.scenes).read_text())["frames"]
    run = json.loads(Path(args.run).read_text())
    first = run.get("first", 0)
    # decisions 11 and 31: the most the build's approximation can be off the
    # ST's (tools/mkrotate.py's ROT_BOUND), and the box an approximated
    # object must be outside (world.6502's NEAR_BOX, the largest collision box)
    rot_bound, near_box = run["rot_bound"], run["near_box"]
    # decision 47: the far-off objects' sentinel
    far_x = run.get("far_x")
    st = {k: 0 for k in ("frames", "list_bad", "rel_bad", "rel_approx", "rel_far", "edges_both", "edges_moved",
                          "only_st", "only_port", "erase_left")}
    worst = 0
    worst_approx = 0
    shown = 0
    spread = collections.Counter()

    def show(msg):
        nonlocal shown
        if shown < args.show:
            print(msg)
        shown += 1

    cycles = {k: [] for k in ("camera", "lists", "objects", "total", "erase")}
    for i, got in enumerate(run["frames"]):
        n = first + i
        exp = scenes[n]["expect"]
        st["frames"] += 1
        for k in cycles:
            if k in got["cycles"]:
                cycles[k].append(got["cycles"][k])
        if got.get("left"):
            st["erase_left"] += 1
            show(f"frame {n}: {got['left']} bytes left on the screen after the erase")
        for name in ("coarse", "near", "draw"):
            if got[name] != exp[name]:
                st["list_bad"] += 1
                show(f"frame {n}: {name} list {got[name]} on the port, {exp[name]} on the ST")
        drawn = set(exp["draw"])
        for slot, v in exp["rel"].items():
            g = got["rel"].get(slot)
            if got.get("exact", {}).get(slot, True):
                if g != v:
                    st["rel_bad"] += 1
                    show(f"frame {n}: slot {slot} camera-space {g} on the port, {v} on the ST")
                continue
            # far off (decision 47): the sentinel in x' and z', for an object
            # the ST has where nothing reads them: neither drawn, nor near,
            # nor in the scanner's square (-&2000 to &2000, both open)
            if far_x is not None and g[0] >> 8 == far_x >> 8 and g[2] >> 8 == far_x >> 8:
                st["rel_far"] += 1
                if (int(slot) in drawn or all(abs(v[i]) <= near_box for i in (0, 2))
                        or all(abs(v[i]) < 0x2000 for i in (0, 2))):
                    st["rel_bad"] += 1
                    show(f"frame {n}: slot {slot} taken as far off, the ST's {v}")
                continue
            # rotated approximately (decision 11): x' and z' within the
            # bound (there's no y': decision 21), and neither drawn by the ST
            # nor near enough in x and z to meet the player
            st["rel_approx"] += 1
            xz = ((g[0], v[0]), (g[2], v[2]))
            off = max(min(abs(a - b), 65536 - abs(a - b)) for a, b in xz)   # words wrap
            worst_approx = max(worst_approx, off)
            if off > rot_bound or int(slot) in drawn or all(abs(v[i]) <= near_box for i in (0, 2)):
                st["rel_bad"] += 1
                show(f"frame {n}: slot {slot} approximated as {g}, the ST's {v}")
        port = {}
        for slot, edge, x0, y0, x1, y1, colour in got["lines"]:
            port[(slot, edge)] = (x0, y0, x1, y1)
        ours = {}
        for o in exp["objects"]:
            if o["exploding"]:
                continue
            for edge, line in zip(o["edges"], o["lines"]):
                ours[(o["slot"], edge)] = tuple(line[:4])
        for key, line in ours.items():
            if key not in port:
                st["only_st"] += 1
                continue
            p = port[key]
            d = round(apart(p, line))
            spread[d] += 1
            st["edges_both"] += 1
            if d:
                st["edges_moved"] += 1
                worst = max(worst, d)
                if d > args.tolerance:
                    show(f"frame {n}: slot {key[0]} edge {key[1]}: {p} on the port, {line} on the ST")
        st["only_port"] += sum(1 for k in port if k not in ours)
    print(" ".join(f"{k} {v}" for k, v in st.items()), f"worst {worst}px, approximation {worst_approx}",
          "apart: " + ", ".join(f"{d}px {n}" for d, n in sorted(spread.items())))
    fields = 39936
    for k, xs in cycles.items():
        if xs:
            print(f"{k:8} mean {statistics.mean(xs):9.0f}  median {statistics.median(xs):9.0f}  "
                  f"max {max(xs):9.0f}  ({statistics.mean(xs) / fields:.2f} fields)")
    bad = st["list_bad"] or st["rel_bad"] or st["erase_left"] or worst > args.tolerance
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
