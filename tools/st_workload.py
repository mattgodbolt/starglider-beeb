#!/usr/bin/env python3
"""Count Starglider's (Atari ST) drawing work per rendered frame in Hatari.

    st_workload.py setup DIR              write DIR/arm.ini and its helpers
    st_workload.py report HATARI.OUT [--split SEG]...
                                          per-segment distributions; --split
                                          reports SEG's frames that drew no
                                          lines as SEG-idle

`setup` writes debugger command files. Send `debug parse DIR/arm.ini`
from a tools/st_hatari.py script once the game is running: it sets a
breakpoint on each routine below, each adding to one of Hatari's virtual
registers V0-V5, and one on frame_end (&08EC2) that prints a sentinel,
the VBL count, the counters and the draw-list length, then zeroes the
counters. Breakpoints don't change the emulated timing, so the VBLs a
frame stay what the game does unwatched.

Mark the parts of a run with `debug echo \\nSEG name\\n`; `report` splits
the frames at those marks.

What is counted (text-segment offsets; Hatari's EmuTOS loads the text at
&109BE, which BASE adds):

- lines: the line drawer's two dispatch jumps, &09172 (y-major, |dy| in
  d3) and &091B8 (x-major, |dx| in d2). Both are reached after clipping, so
  these are lines drawn; the routine plots max(|dx|, |dy|) + 1 pixels, so
  pixels = d3 + 1 or d2 + 1 (low words).
- vertices: transform_vertex &03FFE (a shape's marked vertices); normals:
  &04320 (three vertices a face for the back-face test).
- objects: draw_shape &04B1C plus draw_shape_exploding &04DAC calls, and
  the draw-list length $23E(a6) at the frame's end.
- dots: dot_colour &0976E (ground dots and the like; the scanner plots its
  own dots and isn't counted).
"""
import re
import statistics
import sys
from pathlib import Path

BASE = 0x109BE
SENTINEL = 0xF00D
A6 = 0x5BF00
COUNTERS = [  # (name, virtual register)
    ("lines", "v0"), ("pixels", "v1"), ("vertices", "v2"),
    ("normals", "v3"), ("objects", "v4"), ("dots", "v5"),
]
BREAKS = [  # (offset, file name, commands)
    # (in Hatari expressions parentheses mean indirection, so V6 holds the
    # masked length)
    (0x09172, "line_y.ini", ["r v0='v0+1'", "r v6='d3&$ffff'", "r v1='v1+v6+1'"]),
    (0x091B8, "line_x.ini", ["r v0='v0+1'", "r v6='d2&$ffff'", "r v1='v1+v6+1'"]),
    (0x03FFE, "vert.ini", ["r v2='v2+1'"]),
    (0x04320, "norm.ini", ["r v3='v3+1'"]),
    (0x04B1C, "obj.ini", ["r v4='v4+1'"]),
    (0x04DAC, "obj.ini", None),
    (0x0976E, "dot.ini", ["r v5='v5+1'"]),
]
FRAME_END = 0x08EC2


def setup(d):
    d = Path(d).resolve()
    d.mkdir(parents=True, exist_ok=True)
    arm = ["r v0=0", "r v1=0", "r v2=0", "r v3=0", "r v4=0", "r v5=0"]
    for off, name, cmds in BREAKS:
        if cmds:
            (d / name).write_text("\n".join(cmds) + "\n")
        arm.append(f"b pc = ${BASE + off:x} :trace :quiet :file {d / name}")
    frame = [f"e ${SENTINEL:x}", "e VBL"] + [f"e {v}" for _, v in COUNTERS] + \
            [f"e (${A6 + 0x23E:x}).w"] + [f"r {v}=0" for _, v in COUNTERS]
    (d / "frame.ini").write_text("\n".join(frame) + "\n")
    arm.append(f"b pc = ${BASE + FRAME_END:x} :trace :quiet :file {d / 'frame.ini'}")
    (d / "arm.ini").write_text("\n".join(arm) + "\n")
    print(d / "arm.ini")


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def report(path, split=()):
    text = Path(path).read_text(errors="replace")
    token = re.compile(r"SEG (\S+)|#(-?\d+)(?:/-?\d+)? \(dec\)")
    seg, vals, frames = "start", [], {}
    width = 2 + len(COUNTERS) + 1
    for m in token.finditer(text):
        if m.group(1):
            seg = m.group(1)
            continue
        vals.append(int(m.group(2)))
        if len(vals) >= width and vals[-width] == SENTINEL:
            rec = vals[-width:]
            frames.setdefault(seg, []).append(rec[1:])
            vals = []
    for seg in split:
        recs = frames.get(seg, [])
        # keep each frame's VBL delta with it before separating them
        tagged = [(b[0] - a[0], b) for a, b in zip(recs, recs[1:])]
        frames[seg] = [r for r in tagged if r[1][1]]
        frames[seg + "-idle"] = [r for r in tagged if not r[1][1]]
    names = ["vbl"] + [n for n, _ in COUNTERS] + ["drawlist"]
    print("| Segment | Frames | Measure | Mean | Median | 90th | Max |")
    print("|---|---|---|---|---|---|---|")
    for seg, recs in frames.items():
        if seg == "end" or not recs:
            continue
        if isinstance(recs[0], tuple):          # split above
            vbls = [d for d, _ in recs]
            rows = [r for _, r in recs]
        else:
            # VBLs a frame: the difference between successive frame ends;
            # the first frame's counts began mid-frame, so it's dropped
            vbls = [b[0] - a[0] for a, b in zip(recs, recs[1:])]
            rows = recs[1:]
        cols = {"VBLs a frame": vbls}
        for i, n in enumerate(names[1:], 1):
            cols[n] = [r[i] for r in rows]
        if rows:
            cols["pixels a line"] = [r[2] / r[1] for r in rows if r[1]]
        for k, xs in cols.items():
            if not xs:
                continue
            print(f"| {seg} | {len(rows)} | {k} | {statistics.mean(xs):.1f} | {statistics.median(xs):g} | "
                  f"{pct(xs, 90):g} | {max(xs):g} |")


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("setup", "report"):
        sys.exit(__doc__)
    if sys.argv[1] == "setup":
        setup(sys.argv[2])
    else:
        args = sys.argv[3:]
        report(sys.argv[2], [args[i + 1] for i, a in enumerate(args) if a == "--split"])


if __name__ == "__main__":
    main()
