#!/usr/bin/env python3
"""Drive Hatari headless through its command FIFO: boot an ST disc, then
play a script of key presses, mouse moves, screenshots and debugger
commands, in real time (50 VBLs a second on a PAL ST).

    st_hatari.py SCRIPT --disk IMAGE [--hatari BIN] [--tos IMG] [--out DIR]

Hatari and EmuTOS are not in this project: build Hatari from
https://github.com/hatari/hatari and fetch an etos256*.img from
https://emutos.sourceforge.io, then pass --hatari and --tos (or set
HATARI and HATARI_TOS). Use the protected master (.stx) for Starglider:
the TOSEC .st still has the protection check and halts at &34FC.

SCRIPT lines (blank lines and '#' comments ignored):

    wait SECONDS              let the emulation run
    key K [HOLD]              press and release K (a letter/digit or an ST
                              scancode such as 57 for space); HOLD seconds
    down K / up K             hold or release K
    mouse DX DY               move the mouse by DX, DY
    click [left|right] [HOLD] press and release a mouse button
    shot NAME                 save a screenshot OUT/NAME.png
    debug COMMAND             a Hatari debugger command (e.g. "savebin ...")
    quit

The emulator's own log goes to OUT/hatari.log.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--disk", required=True)
    ap.add_argument("--hatari", default=os.environ.get("HATARI", "hatari"))
    ap.add_argument("--tos", default=os.environ.get("HATARI_TOS"))
    ap.add_argument("--out", default=".")
    ap.add_argument("--memsize", default="1024")
    ap.add_argument("--extra", default="", help="more Hatari options, space separated")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    fifo = out / "hatari.fifo"
    if fifo.exists():
        fifo.unlink()
    cmd = [args.hatari, "--machine", "st", "--memsize", args.memsize,
           "--disk-a", str(Path(args.disk).resolve()), "--fastfdc", "off",
           "--protect-floppy", "on", "--fast-forward", "off", "--frameskips", "0",
           "--confirm-quit", "off", "--statusbar", "off", "--drive-led", "off",
           "--zoom", "1", "--borders", "off", "--sound", "off",
           "--cmd-fifo", str(fifo), "--log-file", str(out / "hatari.log")]
    if args.tos:
        cmd += ["--tos", str(Path(args.tos).resolve())]
    cmd += args.extra.split()
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    proc = subprocess.Popen(cmd, env=env, stdout=open(out / "hatari.out", "w"), stderr=subprocess.STDOUT)
    for _ in range(100):
        if fifo.exists():
            break
        time.sleep(0.05)
    f = open(fifo, "w")

    def send(line):
        f.write(line + "\n")
        f.flush()

    def keyname(k):
        return k if len(k) == 1 else str(int(k, 0))

    try:
        for raw in Path(args.script).read_text().splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            op, *rest = line.split(None, 1)
            arg = rest[0] if rest else ""
            if op == "wait":
                time.sleep(float(arg))
            elif op == "key":
                parts = arg.split()
                send(f"hatari-event keydown {keyname(parts[0])}")
                time.sleep(float(parts[1]) if len(parts) > 1 else 0.1)
                send(f"hatari-event keyup {keyname(parts[0])}")
            elif op == "down":
                send(f"hatari-event keydown {keyname(arg)}")
            elif op == "up":
                send(f"hatari-event keyup {keyname(arg)}")
            elif op == "mouse":
                send(f"hatari-event mousemove {arg}")
            elif op == "click":
                parts = arg.split()
                btn = parts[0] if parts else "left"
                send(f"hatari-event {btn}down")
                time.sleep(float(parts[1]) if len(parts) > 1 else 0.1)
                send(f"hatari-event {btn}up")
            elif op == "shot":
                send(f"hatari-debug screenshot {out / (arg + '.png')}")
            elif op == "debug":
                send(f"hatari-debug {arg}")
            elif op == "quit":
                break
            else:
                sys.exit(f"unknown script step: {raw}")
            time.sleep(0.02)
    finally:
        send("hatari-shortcut quit")
        f.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
