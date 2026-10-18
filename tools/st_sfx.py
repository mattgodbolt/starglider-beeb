#!/usr/bin/env python3
"""Capture Starglider's (Atari ST) sound effects in Hatari: every write to
the YM2149's registers, timed, for each effect the script plays
(docs/research/st.md, "Music and effects").

    st_sfx.py run SCRIPT OUTDIR [--disk ... --hatari ... --tos ...]
    st_sfx.py parse HATARI.OUT OUT.json

SCRIPT is a tools/st_hatari.py script (tests/st/sfx_*.txt) with two more
steps:

    tester          go into the game's own effect tester (&0268A, which
                    nothing calls: each key it reads plays the next effect)
                    at the next frame_end, with the PSG's writes and the
                    VBLs traced from then on
    play E [C]      the tester's next key plays effect E, with d1 = C (1
                    if not given): a breakpoint, once, at its call of
                    sfx_start (&0269E) sets d0 and d1 and logs the moment

`tester` also writes &DF to the byte at &DF. Five of the six Timer A
handlers acknowledge their interrupt with `move.b $DF.l,$FFFFFA0F.l`, an
absolute source where &00228's and the sample player's have the
immediate #$DF; under EmuTOS that byte has bit 5 set, so ISRA's Timer A
bit is never cleared and in software end-of-interrupt mode the MFP passes
nothing of its priority or below again (docs/research/st-logic.md).
Writing &DF there gives them the immediate's effect.

sfx.json: {"clock": the CPU's Hz, "plays": [{"effect", "count", "t"}],
"writes": [[t, reg, value, pc]]}, t in seconds from the first play, pc
an offset into STAR.PRG's text.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = 0x109BE              # where EmuTOS loads the text segment
CLOCK = 8021247             # a PAL ST's CPU: 32.084988 MHz / 4
FRAME_END = 0x08EC2
TESTER = 0x0268A
TESTER_CALL = 0x0269E       # its bsr sfx_start, d0 and d1 set
TAG_PLAY = 0x5A00           # + the play's index


def translate(text, outdir):
    """The script as st_hatari.py takes it, and the plays it makes."""
    out, plays = [], []
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if words and words[0] == "tester":
            enter = outdir / "tester.ini"
            enter.write_text(f"r pc=${BASE + TESTER:x}\n")
            out += ["debug w $df $df",
                    f"debug b pc = ${BASE + FRAME_END:x} :once :trace :quiet :file {enter}",
                    "wait 1",
                    "debug trace psg_write,video_vbl"]
        elif words and words[0] == "play":
            effect = int(words[1], 0)
            count = int(words[2], 0) if len(words) > 2 else 1
            fx = outdir / f"play{len(plays)}.ini"
            fx.write_text(f"e ${TAG_PLAY + len(plays):x}\ne CycleCounter\n"
                          f"r d0=${effect:x}\nr d1=${count:x}\n")
            out += [f"debug b pc = ${BASE + TESTER_CALL:x} :once :trace :quiet :file {fx}", "key x 0.03"]
            plays.append({"effect": effect, "count": count})
        else:
            out.append(line)
    return "\n".join(out) + "\n", plays


def parse(path, plays=None):
    """The plays' moments and the PSG's writes, in CPU cycles: a write's
    from its frame's (the VBL trace's clock at its cycle in the frame) and
    its own cycle in the frame."""
    value = re.compile(r"#(-?\d+)(?:/-?\d+)? \(dec\)")
    vbl = re.compile(r"^VBL \d+ video_cyc=(\d+)")
    clock = re.compile(r"^VBL=\d+ clock=(\d+)")
    write = re.compile(r"^ym write data reg=0x([0-9a-f]+) val=0x([0-9a-f]+) video_cyc=(\d+) .* pc=([0-9a-f]+)")
    found, writes, pending = {}, [], []
    frame, vbl_cyc, last, frame_len = None, 0, 0, 160256
    for line in Path(path).read_text(errors="replace").splitlines():
        if m := vbl.match(line):
            vbl_cyc = int(m.group(1))
            continue
        if m := clock.match(line):
            start = int(m.group(1)) - vbl_cyc
            if frame is not None and start > frame:
                frame_len = start - frame
            frame = start
            continue
        if m := write.match(line):
            if frame is None:
                continue
            t = frame + int(m.group(3))
            if t < last:                    # past the frame's end, before its VBL's line
                t += frame_len
            last = t
            writes.append([t, int(m.group(1), 16), int(m.group(2), 16), int(m.group(4), 16) - BASE])
            continue
        if m := value.search(line):
            pending.append(int(m.group(1)))
            if TAG_PLAY <= pending[0] < TAG_PLAY + 256:
                if len(pending) == 2:
                    found[pending[0] - TAG_PLAY] = pending[1] & 0xFFFFFFFF
                    pending = []
            else:
                pending = []
    if plays is None:
        plays = [{} for _ in found]
    out = []
    for i, p in enumerate(plays):
        if i not in found:
            sys.exit(f"{path}: play {i} never reached the tester's call")
        out.append(dict(p, cycle=found[i]))
    t0 = out[0]["cycle"]
    return {
        "clock": CLOCK,
        "plays": [dict({k: v for k, v in p.items() if k != "cycle"}, t=(p["cycle"] - t0) / CLOCK) for p in out],
        "writes": [[(t - t0) / CLOCK, r, v, pc] for t, r, v, pc in writes if t >= t0],
    }


def run(script, outdir, rest):
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    text, plays = translate(Path(script).read_text(), outdir)
    (outdir / "script.txt").write_text(text)
    (outdir / "plays.json").write_text(json.dumps(plays))
    here = Path(__file__).resolve().parent
    subprocess.run([sys.executable, "-I", str(here / "st_hatari.py"), str(outdir / "script.txt"),
                    "--out", str(outdir), *rest], check=True)
    save(parse(outdir / "hatari.out", plays), outdir / "sfx.json")


def save(data, out):
    Path(out).write_text(json.dumps(data))
    print(f"{out}: {len(data['plays'])} plays, {len(data['writes'])} writes")


def main():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == "run":
        run(a[1], a[2], a[3:])
    elif len(a) == 3 and a[0] == "parse":
        plays = Path(a[1]).with_name("plays.json")
        save(parse(a[1], json.loads(plays.read_text()) if plays.exists() else None), a[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    main()
