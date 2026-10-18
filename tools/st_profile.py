#!/usr/bin/env python3
"""Profile Starglider (Atari ST) in Hatari, and split its time by what it's
doing.

    st_profile.py run SCRIPT OUTDIR       profile a tools/st_hatari.py script
                                          (tests/st/profile_*.txt): {out} in
                                          it stands for OUTDIR
    st_profile.py split PROFILE           the time by area

Hatari's CPU profiler (`profile on`, `profile save FILE`) counts cycles
at every address. A profile saved through the command FIFO is empty in
Hatari as it stands, because only entering the debugger processes the
data; the Hatari built in ../hatari is patched to process it on saving
(docs/research/st.md, "Running it in Hatari").

The areas are ranges of text-segment offsets (Hatari's EmuTOS loads the
text at &109BE), from what docs/research/st.md found in each.
"""
import re
import subprocess
import sys
from pathlib import Path

BASE = 0x109BE
AREAS = [  # (area, group, from, to)
    ("sound effects, VBL", "other", 0x00000, 0x00C32),
    ("input, score and message printing", "text", 0x00C32, 0x01A50),
    ("sample player", "other", 0x01A50, 0x01E5A),
    ("main loop, warnings", "logic", 0x01E5A, 0x0270E),
    ("keys, commands", "logic", 0x0270E, 0x032EC),
    ("title, interrogate", "other", 0x032EC, 0x03FFE),
    ("transform, matrix", "drawing", 0x03FFE, 0x04320),
    ("back-face vertices", "drawing", 0x04320, 0x043EE),
    ("animate shapes", "logic", 0x043EE, 0x04692),
    ("random numbers", "logic", 0x04692, 0x047AA),
    ("ground dots, their set-up", "dots", 0x047AA, 0x04B1C),
    ("draw_shape: faces, edges", "drawing", 0x04B1C, 0x04D66),
    ("projecting edges", "drawing", 0x04D66, 0x04FE8),
    ("world_render, sight", "drawing", 0x04FE8, 0x0561C),
    ("coarse and draw lists", "drawing", 0x0561C, 0x05872),
    ("panel: waveforms, gauges, scanner", "panel", 0x05872, 0x077B4),
    ("flight", "logic", 0x077B4, 0x07A54),
    ("handlers, missiles, enemy fire", "logic", 0x07A54, 0x08390),
    ("bearing, collisions, docking, laser", "logic", 0x08390, 0x08CA0),
    ("frame end, palettes", "other", 0x08CA0, 0x08FE6),
    ("lines", "drawing", 0x08FE6, 0x0976E),
    ("dots, the sight's bitmap", "dots", 0x0976E, 0x099CA),
    ("clearing the view", "drawing", 0x099CA, 0x0A170),
    ("clipping to the window", "drawing", 0x0A170, 0x0A374),
    ("clipping at z = 2", "drawing", 0x0A374, 0x0A520),
    ("waiting for the raster, swapping", "waiting", 0x0A520, 0x0A5DC),
    ("other", "other", 0x0A5DC, 0x0A6AE),
    ("level set-up", "logic", 0x0A6AE, 0x0ABF6),
]
LINE = re.compile(r"^\$?([0-9A-Fa-f]+) .*% \(([^)]*)\)$")


def split(path):
    total, by_area, by_group = 0, {}, {}
    for line in Path(path).read_text(errors="replace").splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        cycles = int(m.group(2).split(",")[1])
        total += cycles
        off = int(m.group(1), 16) - BASE
        area, group = "outside the program (TOS, interrupts)", "other"
        for name, g, lo, hi in AREAS:
            if lo <= off < hi:
                area, group = name, g
                break
        by_area[area] = by_area.get(area, 0) + cycles
        by_group[group] = by_group.get(group, 0) + cycles
    if not total:
        sys.exit(f"{path}: no profile data (is Hatari patched? see the docstring)")
    print("| Group | Share |\n|---|---|")
    for g, c in sorted(by_group.items(), key=lambda x: -x[1]):
        print(f"| {g} | {100 * c / total:.1f}% |")
    print("\n| Area | Share |\n|---|---|")
    for a, c in sorted(by_area.items(), key=lambda x: -x[1]):
        print(f"| {a} | {100 * c / total:.1f}% |")
    print(f"\n{total} cycles profiled")


def run(script, outdir, rest):
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    text = Path(script).read_text().replace("{out}", str(outdir))
    (outdir / "script.txt").write_text(text)
    here = Path(__file__).resolve().parent
    subprocess.run([sys.executable, "-I", str(here / "st_hatari.py"), str(outdir / "script.txt"),
                    "--out", str(outdir), *rest], check=True)
    split(outdir / "profile.txt")


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "split":
        split(a[1])
    elif len(a) >= 3 and a[0] == "run":
        run(a[1], a[2], a[3:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
