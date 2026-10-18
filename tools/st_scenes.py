#!/usr/bin/env python3
"""Capture Starglider's (Atari ST) scenes in Hatari: each rendered frame's
state and every line it drew, for the port's renderer to draw again.

    st_scenes.py setup DIR             write DIR/arm.ini and its helpers
    st_scenes.py parse HATARI.OUT OUT.json
    st_scenes.py run SCRIPT OUTDIR     setup, tools/st_hatari.py, parse:
                                       OUTDIR/scenes.json

SCRIPT is a tools/st_hatari.py script in which `{arm}` stands for the
path of arm.ini (tests/st/*.txt): send `debug parse {arm}` once the game
is running. `run` takes --disk, --hatari and --tos as st_hatari.py does,
from the same environment variables.

The breakpoints (text-segment offsets; EmuTOS loads the text at &109BE):

- &05108, in world_render just after the near and draw lists are built:
  a FRAME record (the VBL count), then memory dumps of the variable block
  and the object table ($0-$359A(a6)), the shape table (its vertex
  offsets are the animations' current frames), the silo's two objects
  (&1218, &1258), the mouse accumulators and the energy beam's face colour
  (animate_shapes cycles it, &044F4). So a frame holds the
  renderer's inputs (the player, every object, the animation frames) and
  the ST's own intermediate results (the camera matrix, the lists, each
  object's camera-space position), all as they were when it drew.
- draw_shape (&04B1C) and draw_shape_exploding (&04DAC): an OBJECT
  record, the object's address (a4), so the lines after it are its own.
- the line drawer (&09128), after both clips: a LINE record, x0 y0 x1 y1
  (d4-d7) and the colour ($208(a6)).
- &05166, after the last object: an AFTER record, so the lines after it
  (the lasers, enemy fire) are kept apart from the last object's.

Breakpoints don't change the emulated timing (docs/research/st.md, "Work
per frame"), but the dumps make Hatari slower than real time, so a
script's waits cover fewer frames than they would unwatched.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = 0x109BE
A6 = 0x5BF00
FRAME, OBJECT, LINE, AFTER = 0xF00D, 0x0B1E, 0x11E0, 0xAF7E
AFTER_LISTS = 0x05108
DRAW_SHAPE, DRAW_EXPLODING = 0x04B1C, 0x04DAC
LINE_DRAWER = 0x09128
AFTER_OBJECTS = 0x05166
# (name, address, length): what each FRAME dumps
REGIONS = [
    ("vars", A6, 0x359A),                       # variables, lists, 140 objects
    ("shapes", BASE + 0x0AF4E, 29 * 16),        # the shape table
    ("silo", 0x1218, 0x80),                     # the tunnel and its missile
    ("mouse", BASE + 0x01842, 12),              # the mouse accumulators
    ("beam", BASE + 0x0D97E, 2),                # the beam's face colour, cycled each frame
]


def setup(d):
    d = Path(d).resolve()
    d.mkdir(parents=True, exist_ok=True)
    frame = [f"e ${FRAME:x}", "e VBL"] + [f"m ${a:x}-${a + n:x}" for _, a, n in REGIONS]
    (d / "frame.ini").write_text("\n".join(frame) + "\n")
    (d / "obj.ini").write_text(f"e ${OBJECT:x}\ne a4\n")
    (d / "after.ini").write_text(f"e ${AFTER:x}\n")
    (d / "line.ini").write_text(f"e ${LINE:x}\ne d4&$ffff\ne d5&$ffff\ne d6&$ffff\ne d7&$ffff\n"
                                f"e (${A6 + 0x208:x}).w\n")
    arm = [f"b pc = ${BASE + AFTER_LISTS:x} :trace :quiet :file {d / 'frame.ini'}",
           f"b pc = ${BASE + DRAW_SHAPE:x} :trace :quiet :file {d / 'obj.ini'}",
           f"b pc = ${BASE + DRAW_EXPLODING:x} :trace :quiet :file {d / 'obj.ini'}",
           f"b pc = ${BASE + LINE_DRAWER:x} :trace :quiet :file {d / 'line.ini'}",
           f"b pc = ${BASE + AFTER_OBJECTS:x} :trace :quiet :file {d / 'after.ini'}"]
    (d / "arm.ini").write_text("\n".join(arm) + "\n")
    return d / "arm.ini"


def signed(v):
    return v - 0x10000 if v & 0x8000 else v


def parse(path):
    """The frames in a Hatari output, in order. The first is dropped if its
    dumps are incomplete (the breakpoints were set mid-frame)."""
    value = re.compile(r"#(-?\d+)(?:/-?\d+)? \(dec\)")
    dump = re.compile(r"^([0-9A-F]{8}): ((?:[0-9a-f]{2} )+)")
    seg = re.compile(r"^SEG (\S+)")
    frames, cur, pending, segment = [], None, [], "start"
    mem = {}

    def finish():
        if cur is not None:
            cur["memory"] = {}
            for name, addr, n in REGIONS:
                data = bytes(mem.get(addr + i, 0) for i in range(n))
                cur["memory"][name] = data.hex()
            frames.append(cur)

    for line in Path(path).read_text(errors="replace").splitlines():
        if m := seg.match(line):
            segment = m.group(1)
            continue
        if m := dump.match(line):
            addr = int(m.group(1), 16)
            for i, b in enumerate(m.group(2).split()):
                mem[addr + i] = int(b, 16)
            continue
        m = value.search(line)
        if not m:
            continue
        pending.append(int(m.group(1)))
        tag = pending[0]
        if tag == FRAME and len(pending) == 2:
            finish()
            cur = {"segment": segment, "vbl": pending[1], "lines": []}
            mem = {}
            pending = []
        elif tag == OBJECT and len(pending) == 2:
            if cur is not None:
                cur["lines"].append({"object": pending[1]})
            pending = []
        elif tag == AFTER:
            if cur is not None:
                cur["lines"].append({"object": "after"})
            pending = []
        elif tag == LINE and len(pending) == 6:
            if cur is not None:
                x0, y0, x1, y1 = (signed(v) for v in pending[1:5])
                cur["lines"].append([x0, y0, x1, y1, pending[5] & 0xFFFF])
            pending = []
        elif tag not in (FRAME, OBJECT, LINE, AFTER):
            pending = []                            # some other output
    finish()
    # each frame's lines were drawn after its dump; regroup them by object
    # ("object" is its address, or "after" for what follows the objects)
    for f in frames:
        objects, current = [], {"object": None, "lines": []}
        for item in f.pop("lines"):
            if isinstance(item, dict):
                if current["lines"] or current["object"] is not None:
                    objects.append(current)
                current = {"object": item["object"], "lines": []}
            else:
                current["lines"].append(item)
        objects.append(current)
        f["drawn"] = objects
    return frames[1:] if frames else frames


def run(script, outdir, rest):
    outdir = Path(outdir).resolve()
    arm = setup(outdir)
    text = Path(script).read_text().replace("{arm}", str(arm))
    (outdir / "script.txt").write_text(text)
    here = Path(__file__).resolve().parent
    subprocess.run([sys.executable, "-I", str(here / "st_hatari.py"), str(outdir / "script.txt"),
                    "--out", str(outdir), *rest], check=True)
    frames = parse(outdir / "hatari.out")
    (outdir / "scenes.json").write_text(json.dumps({"regions": REGIONS, "frames": frames}))
    print(f"{outdir / 'scenes.json'}: {len(frames)} frames")


def main():
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "setup":
        print(setup(a[1]))
    elif len(a) == 3 and a[0] == "parse":
        frames = parse(a[1])
        Path(a[2]).write_text(json.dumps({"regions": REGIONS, "frames": frames}))
        print(f"{a[2]}: {len(frames)} frames")
    elif len(a) >= 3 and a[0] == "run":
        run(a[1], a[2], a[3:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    main()
