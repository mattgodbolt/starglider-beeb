#!/usr/bin/env python3
"""Drive a headless Caprice32 (with the research harness patch) through a CPC disc.

    cpc_emu.py --out DIR [--cap32 PATH] [--disc DSK] [--run NAME] STEP...

Steps, in order (the play.mjs style of ../porting-to-the-beeb.md):

    fN          advance N 50Hz frames (frame 0 is power-on)
    @N          advance to absolute frame N
    KEY:down    press a CPC key (names below), KEY:up releases it
    KEY:tap     press for 4 frames then release (advances 6 frames)
    !shot:NAME  save the emulator's screen (with border) as DIR/NAME.png
    !ram:NAME   save all RAM as DIR/NAME.ram (128K on a 6128; bank 0 first)
    !sna:NAME   save a Caprice32 snapshot DIR/NAME.sna
    !regs       print PC, SP, mode, inks and CRTC registers
    !poke:ADDR=VAL  write a byte (hex) into the CPU's current memory map
    !covon, !covoff, !covclear, !cov:NAME
                execution profile: per address, instructions started and
                microseconds spent (2 x 65536 little-endian uint32 in DIR/NAME.cov)
    !exit       stop (added at the end if missing)

Every OUT to the gate array, the CRTC and the PPI is logged in DIR/ports.log as
"frame scanline pc port value". The harness patch lives in the Caprice32
checkout (src/cap32.cpp, src/z80.cpp: search for "harness"); the disc is
booted with RUN"NAME typed by Caprice32's autocmd, so frame numbers are
repeatable from run to run.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

KEYS = {}
_MATRIX = [
    ["CURUP", "CURRIGHT", "CURDOWN", "F9", "F6", "F3", "ENTER", "FDOT"],
    ["CURLEFT", "COPY", "F7", "F8", "F5", "F1", "F2", "F0"],
    ["CLR", "LBRACKET", "RETURN", "RBRACKET", "F4", "SHIFT", "BACKSLASH", "CTRL"],
    ["CARET", "MINUS", "AT", "P", "SEMICOLON", "COLON", "SLASH", "DOT"],
    ["0", "9", "O", "I", "L", "K", "M", "COMMA"],
    ["8", "7", "U", "Y", "H", "J", "N", "SPACE"],
    ["6", "5", "R", "T", "G", "F", "B", "V"],
    ["4", "3", "E", "W", "S", "D", "C", "X"],
    ["1", "2", "ESC", "Q", "TAB", "A", "CAPS", "Z"],
    ["JUP", "JDOWN", "JLEFT", "JRIGHT", "JFIRE2", "JFIRE1", "JFIRE3", "DEL"],
]
for _row, _names in enumerate(_MATRIX):
    for _bit, _name in enumerate(_names):
        KEYS[_name] = (_row, _bit)

HERE = Path(__file__).resolve().parent
DEFAULT_CAP32 = Path.home() / "dev" / "caprice32" / "cap32"


def compile_steps(steps, out):
    frame = 0
    lines = []
    for step in steps:
        if step.startswith("f") and step[1:].isdigit():
            frame += int(step[1:])
        elif step.startswith("@"):
            frame = int(step[1:])
        elif step.startswith("!"):
            op, _, arg = step[1:].partition(":")
            if op == "poke":
                addr, _, val = arg.partition("=")
                lines.append(f"{frame} poke {addr} {val}")
            elif op in ("shot", "ram", "sna", "cov"):
                ext = {"shot": "png", "ram": "ram", "sna": "sna", "cov": "cov"}[op]
                lines.append(f"{frame} {op} {out / f'{arg}.{ext}'}")
            else:
                lines.append(f"{frame} {op}")
        elif ":" in step:
            name, _, action = step.rpartition(":")
            row, bit = KEYS[name.upper()]
            if action == "tap":
                lines.append(f"{frame} keydown {row} {bit}")
                lines.append(f"{frame + 4} keyup {row} {bit}")
                frame += 6
            else:
                lines.append(f"{frame} key{action} {row} {bit}")
        else:
            raise SystemExit(f"unknown step {step!r}")
    if not any(line.endswith(" exit") for line in lines):
        lines.append(f"{frame} exit")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--cap32", type=Path, default=DEFAULT_CAP32)
    ap.add_argument("--cfg", type=Path, help="Caprice32 config (default: written into --out)")
    ap.add_argument("--disc", type=Path, default=HERE.parent / "original" / "cpc" / "Starglider.dsk")
    ap.add_argument("--run", default="starglid")
    ap.add_argument("steps", nargs="+")
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    cap32 = args.cap32.resolve()
    cfg = args.cfg
    if cfg is None:
        cfg = out / "cap32.cfg"
        base = (cap32.parent / "cap32.cfg").read_text()
        repl = {"scr_fps=1": "scr_fps=0", "enabled=1": "enabled=0",
                "rom_path=": f"rom_path={cap32.parent / 'rom'}",
                "resources_path=": f"resources_path={cap32.parent / 'resources'}"}
        lines = []
        for line in base.splitlines():
            lines.append(repl.get(line, line))
        text = "\n".join(lines) + "\n"
        text = text.replace("[system]\n", "[system]\nlimit_speed=0\n", 1)
        cfg.write_text(text)
    script = out / "script.txt"
    script.write_text("\n".join(compile_steps(args.steps, out)) + "\n")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
               CAP32_SCRIPT=str(script), CAP32_PORTLOG=str(out / "ports.log"))
    proc = subprocess.run([str(cap32), "-c", str(cfg), "-a", f'run"{args.run}', str(args.disc.resolve())],
                          env=env, cwd=out, capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if line.startswith("frame "):
            print(line)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
