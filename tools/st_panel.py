#!/usr/bin/env python3
"""Capture Starglider's (Atari ST) panel in Hatari: each frame's state as
the panel draws it, and the screen it makes, for tools/panelcheck.mjs --st
to check its model of the ST's panel against.

    st_panel.py run SCRIPT OUTDIR      tools/st_hatari.py, then parse:
                                       OUTDIR/panel.json
    st_panel.py parse HATARI.OUT OUT.json

SCRIPT is a tools/st_hatari.py script in which `{arm}` stands for the
path of the breakpoints' file (tests/st/panel_*.txt): `debug parse {arm}`
once the game is running. `run` takes --disk, --hatari and --tos as
st_hatari.py does.

Each frame has three points: `wave` at the waveforms' entry (&05872),
with tools/st_steps.py's regions dumped (the state the panel draws from);
`collide` and `end` (after collisions and after frame_end: what decides
the logic's texts); and the frame's screen, dumped at the next frame's
top (&01F10), from the buffer frame_end showed ($4(a6)): by then the
post-frame tests have printed on it too.

panel.json: {"regions": [...], "frames": [{"points": {point: {region:
hex}}, "a0": {...}, "screen": hex (32000 bytes)}]}.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_steps  # noqa: E402

BASE, A6, REGIONS = st_steps.BASE, st_steps.A6, st_steps.REGIONS
POINTS = [("wave", 0x05872), ("collide", 0x01F28), ("end", 0x01F30), ("mine", 0x07B28)]
TOP = 0x01F10
SCREENS = (0x70000, 0x78000)                # the ST's two buffers (docs/research/st-panel.md)
TAG_POINT, TAG_SCREEN = 0x5900, 0x5980


def setup(d):
    d = Path(d).resolve()
    d.mkdir(parents=True, exist_ok=True)
    dumps = [f"m ${a:x}-${a + n:x}" for _, a, n in REGIONS]
    arm = []
    for i, (name, off) in enumerate(POINTS):
        a0 = ["e a0"] if name == "mine" else []
        (d / f"{name}.ini").write_text("\n".join([f"e ${TAG_POINT + i:x}"] + a0 + dumps) + "\n")
        arm.append(f"b pc = ${BASE + off:x} :trace :quiet :file {d / (name + '.ini')}")
    for k, s in enumerate(SCREENS):
        (d / f"screen{k}.ini").write_text(f"e ${TAG_SCREEN + k:x}\nm ${s:x}-${s + 32000:x}\n")
        arm.append(f"b pc = ${BASE + TOP:x} && ($5bf04).l = ${s:x} :trace :quiet :file {d / f'screen{k}.ini'}")
    (d / "arm.ini").write_text("\n".join(arm) + "\n")
    return d / "arm.ini"


def parse(path):
    value = re.compile(r"#(-?\d+)(?:/-?\d+)? \(dec\)")
    dump = re.compile(r"^([0-9A-F]{8}): ((?:[0-9a-f]{2} )+)")
    frames, cur = [], None
    kind, mem, pending = None, {}, []

    def close():
        if kind is None:
            return
        if kind[0] == "screen":
            s = SCREENS[kind[1]]
            data = [mem.get(s + i) for i in range(32000)]
            if all(b is not None for b in data) and frames:
                frames[-1]["screen"] = bytes(data).hex()
            return
        if cur is None:
            return
        out = {}
        for name, addr, n in REGIONS:
            data = [mem.get(addr + i) for i in range(n)]
            if any(b is None for b in data):
                return
            out[name] = bytes(data).hex()
        cur["points"][kind[1]] = out

    for line in Path(path).read_text(errors="replace").splitlines():
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
        if TAG_POINT <= tag < TAG_POINT + len(POINTS):
            name = POINTS[tag - TAG_POINT][0]
            if len(pending) < (2 if name == "mine" else 1):
                continue
            close()
            if name == "wave":
                if cur is not None:
                    frames.append(cur)
                cur = {"points": {}, "a0": {}}
            if cur is not None and name == "mine":
                cur["a0"]["mine"] = pending[1] & 0xFFFFFFFF
            kind, mem, pending = ("point", name), {}, []
        elif TAG_SCREEN <= tag < TAG_SCREEN + len(SCREENS):
            close()
            if cur is not None:
                frames.append(cur)
                cur = None
            kind, mem, pending = ("screen", tag - TAG_SCREEN), {}, []
        else:
            pending = []
    close()
    # a frame is whole with its points and the screen after it
    return [f for f in frames if "screen" in f and "wave" in f["points"]]


def write(frames, out):
    Path(out).write_text(json.dumps({"regions": REGIONS, "frames": frames}))
    print(f"{out}: {len(frames)} frames")


def run(script, outdir, rest):
    outdir = Path(outdir).resolve()
    arm = setup(outdir)
    (outdir / "script.txt").write_text(Path(script).read_text().replace("{arm}", str(arm)))
    here = Path(__file__).resolve().parent
    subprocess.run([sys.executable, "-I", str(here / "st_hatari.py"), str(outdir / "script.txt"),
                    "--out", str(outdir), *rest], check=True)
    write(parse(outdir / "hatari.out"), outdir / "panel.json")


def main():
    a = sys.argv[1:]
    if len(a) == 3 and a[0] == "parse":
        write(parse(a[1]), a[2])
    elif len(a) >= 3 and a[0] == "run":
        run(a[1], a[2], a[3:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
