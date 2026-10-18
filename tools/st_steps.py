#!/usr/bin/env python3
"""Capture Starglider's (Atari ST) logic in Hatari, routine by routine, for
the port's logic to be checked against (decision 1).

    st_steps.py setup DIR              write DIR/arm.ini and its helpers
    st_steps.py parse HATARI.OUT OUT.json
    st_steps.py run SCRIPT OUTDIR      setup, tools/st_hatari.py, parse:
                                       OUTDIR/steps.json

SCRIPT is a tools/st_hatari.py script in which `{arm}` stands for the
path of arm.ini (tests/st/steps_*.txt): send `debug parse {arm}` once the
game is running. `run` takes --disk, --hatari and --tos as st_hatari.py
does. Fly with the keys, not the mouse: random8 adds the mouse
accumulator, which the keys change only inside read_keys.

At each routine boundary of the frame loop (&01F10) the state the logic
keeps is dumped (REGIONS: the variable block with the objects, the low RAM
and the program's own data that docs/research/st-logic.md lists), so a
routine of the port's can be started from the state the ST's started
from, and its result compared with the state the ST's left:

    top      &01F10  the frame's start (world_render's entry)
    lists    &05108  in world_render, after the lists
    render   &01F14  after world_render (read_keys' entry)
    keys     &01F18  after read_keys
    flight   &01F1C  after player_flight
    handlers &01F20  after object_handlers
    animate  &01F24  after animate_shapes
    collide  &01F28  after collisions
    message  &01F2C  after level_message
    end      &01F30  after frame_end (the post-frame tests' entry)

The next frame's `top` is the post-frame tests' result. Every call of
random8 (&046B2) and random32 (&04692) is logged with d0 (which random8
adds to its state: some callers leave it over from earlier work) and the
caller, so a transcription can see what it must reproduce.

steps.json: {"regions": [[name, address, length]...], "points": [...],
"frames": [{"vbl", "segment", "points": {point: {region: hex}}, "rng":
[[routine, d0, caller]...]}]}.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = 0x109BE
A6 = 0x5BF00
POINTS = [  # (name, text offset)
    ("top", 0x01F10), ("lists", 0x05108), ("render", 0x01F14), ("keys", 0x01F18),
    ("flight", 0x01F1C), ("handlers", 0x01F20), ("animate", 0x01F24), ("collide", 0x01F28),
    ("message", 0x01F2C), ("end", 0x01F30),
]
TAG_POINT = 0x5700                      # + the point's index
TAG_RANDOM8, TAG_RANDOM32 = 0x5800, 0x5801
RANDOM8, RANDOM32 = 0x046B2, 0x04692
# (name, address, length): what each point dumps
REGIONS = [
    ("vars", A6, 0x359A),                       # the variable block and the 140 objects
    ("free", 0x94C, 4 * 140),                   # the free-record stack (it grows past ten)
    ("silo", 0x1218, 0x80),                     # the tunnel and its missile
    ("vbl", 0x1E4, 2),                          # the VBL count
    ("sfxlock", 0x29C, 2),                      # VBLs until another effect may start
    ("sample", 0xA0, 8),                        # the sample's start and length
    ("timera", 0x2CF, 2),                       # its Timer A control and data
    ("score", BASE + 0x0150C, 16),              # the score (BCD), and the longs after it
    ("input", BASE + 0x017C2, 0x92),            # key states, the mouse accumulators, the last key
    ("sfx", BASE + 0x019F0, 0x18),              # the print colour and the effects' state
    ("addend", BASE + 0x01A4C, 4),              # the score add's d0
    ("sampleptr", BASE + 0x01B00, 4),           # the sample player's pointer
    ("sampleleft", BASE + 0x01E56, 4),          # sample bytes still to play
    ("shapes", BASE + 0x0AF4E, 29 * 16),        # the shape table (the animations' frames)
    ("frames", BASE + 0x0C17E, 8), ("frames1", BASE + 0x0D6CE, 8), ("frames2", BASE + 0x0FD4C, 8),
    ("frames3", BASE + 0x0D99C, 8), ("frames4", BASE + 0x10768, 8), ("frames5", BASE + 0x11C18, 8),
    ("frames6", BASE + 0x1204C, 8),             # the seven frame lists' heads
    ("beam", BASE + 0x0D97E, 2),                # the beam's face colour, cycled each frame
    ("scanner", BASE + 0x06006, 32),            # the scanner's colours by type (11's is the beam's)
]


def setup(d):
    d = Path(d).resolve()
    d.mkdir(parents=True, exist_ok=True)
    dumps = [f"m ${a:x}-${a + n:x}" for _, a, n in REGIONS]
    arm = []
    for i, (name, off) in enumerate(POINTS):
        (d / f"{name}.ini").write_text("\n".join([f"e ${TAG_POINT + i:x}", "e VBL"] + dumps) + "\n")
        arm.append(f"b pc = ${BASE + off:x} :trace :quiet :file {d / (name + '.ini')}")
    for tag, off, name in ((TAG_RANDOM8, RANDOM8, "random8"), (TAG_RANDOM32, RANDOM32, "random32")):
        (d / f"{name}.ini").write_text(f"e ${tag:x}\ne d0&$ffff\ne (a7).l\n")
        arm.append(f"b pc = ${BASE + off:x} :trace :quiet :file {d / (name + '.ini')}")
    (d / "arm.ini").write_text("\n".join(arm) + "\n")
    return d / "arm.ini"


def parse(path):
    """The frames in a Hatari output, in order, each from a `top` to the
    next. The first is dropped (the breakpoints were set mid-frame), and
    a point whose dumps are incomplete is left out."""
    value = re.compile(r"#(-?\d+)(?:/-?\d+)? \(dec\)")
    dump = re.compile(r"^([0-9A-F]{8}): ((?:[0-9a-f]{2} )+)")
    seg = re.compile(r"^SEG (\S+)")
    frames, cur, pending, segment = [], None, [], "start"
    point, mem = None, {}

    def close_point():
        if cur is None or point is None:
            return
        out = {}
        for name, addr, n in REGIONS:
            data = [mem.get(addr + i) for i in range(n)]
            if any(b is None for b in data):
                return
            out[name] = bytes(data).hex()
        cur["points"][point] = out

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
        if TAG_POINT <= tag < TAG_POINT + len(POINTS) and len(pending) == 2:
            close_point()
            name = POINTS[tag - TAG_POINT][0]
            if name == "top":
                if cur is not None:
                    frames.append(cur)
                cur = {"segment": segment, "vbl": pending[1], "points": {}, "rng": []}
            point, mem, pending = name, {}, []
        elif tag in (TAG_RANDOM8, TAG_RANDOM32) and len(pending) == 3:
            if cur is not None:
                cur["rng"].append(["random8" if tag == TAG_RANDOM8 else "random32",
                                   pending[1] & 0xFFFF, (pending[2] & 0xFFFFFFFF) - BASE])
            pending = []
        elif not (TAG_POINT <= tag < TAG_POINT + len(POINTS)) and tag not in (TAG_RANDOM8, TAG_RANDOM32):
            pending = []                            # some other output
    close_point()
    if cur is not None:
        frames.append(cur)
    return frames[1:]


def write(frames, out):
    Path(out).write_text(json.dumps({"regions": REGIONS, "points": [p for p, _ in POINTS], "frames": frames}))
    print(f"{out}: {len(frames)} frames")


def run(script, outdir, rest):
    outdir = Path(outdir).resolve()
    arm = setup(outdir)
    text = Path(script).read_text().replace("{arm}", str(arm))
    (outdir / "script.txt").write_text(text)
    here = Path(__file__).resolve().parent
    subprocess.run([sys.executable, "-I", str(here / "st_hatari.py"), str(outdir / "script.txt"),
                    "--out", str(outdir), *rest], check=True)
    write(parse(outdir / "hatari.out"), outdir / "steps.json")


def main():
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "setup":
        print(setup(a[1]))
    elif len(a) == 3 and a[0] == "parse":
        write(parse(a[1]), a[2])
    elif len(a) >= 3 and a[0] == "run":
        run(a[1], a[2], a[3:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    main()
