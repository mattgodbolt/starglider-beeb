#!/usr/bin/env python3
"""Compare the port's renderer on captured scenes (tools/scenerun.mjs) with
the ST's (tools/mkscene.py's expectations, from tools/st_render.py).

    scenecheck.py SCENES.json RUN.json [--show N] [--tolerance PX]

The lists and the camera-space positions are the game's logic: they must
match exactly. Lines are compared by object and edge: an edge drawn by one
and not the other is a culling difference (decision 9 moves the test into
object space); an edge both draw must match end to end, within
--tolerance pixels (0 while the drawing follows the ST's arithmetic).
Prints a summary and the cycles each part took, and exits non-zero on a
difference the rules don't allow.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path


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
    st = {k: 0 for k in ("frames", "list_bad", "rel_bad", "edges_both", "edges_moved", "only_st", "only_port")}
    worst = 0
    shown = 0

    def show(msg):
        nonlocal shown
        if shown < args.show:
            print(msg)
        shown += 1

    cycles = {k: [] for k in ("camera", "lists", "objects", "total")}
    for i, got in enumerate(run["frames"]):
        n = first + i
        exp = scenes[n]["expect"]
        st["frames"] += 1
        for k in cycles:
            cycles[k].append(got["cycles"][k])
        for name in ("coarse", "near", "draw"):
            if got[name] != exp[name]:
                st["list_bad"] += 1
                show(f"frame {n}: {name} list {got[name]} on the port, {exp[name]} on the ST")
        for slot, v in exp["rel"].items():
            g = got["rel"].get(slot)
            if g != v:
                st["rel_bad"] += 1
                show(f"frame {n}: slot {slot} camera-space {g} on the port, {v} on the ST")
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
            d = max(abs(a - b) for a, b in zip(p, line))
            # the same line either way round
            d = min(d, max(abs(a - b) for a, b in zip(p, line[2:] + line[:2])))
            st["edges_both"] += 1
            if d:
                st["edges_moved"] += 1
                worst = max(worst, d)
                if d > args.tolerance:
                    show(f"frame {n}: slot {key[0]} edge {key[1]}: {p} on the port, {line} on the ST")
        st["only_port"] += sum(1 for k in port if k not in ours)
    print(" ".join(f"{k} {v}" for k, v in st.items()), f"worst {worst}px")
    fields = 39936
    for k, xs in cycles.items():
        if xs:
            print(f"{k:8} mean {statistics.mean(xs):9.0f}  median {statistics.median(xs):9.0f}  "
                  f"max {max(xs):9.0f}  ({statistics.mean(xs) / fields:.2f} fields)")
    bad = st["list_bad"] or st["rel_bad"] or worst > args.tolerance
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
