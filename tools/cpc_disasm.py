#!/usr/bin/env python3
"""Disassemble a RAM dump of CPC Starglider with SkoolKit, guided by execution profiles.

    cpc_disasm.py RAM OUTDIR COV [COV...]

RAM is a dump from tools/cpc_emu.py (`!ram:NAME`; the first 64K is the CPU's
view while the game runs with RAM configuration &C0). Each COV is an execution
profile from the same tool (`!covon` ... `!cov:NAME`). Every address any
profile started an instruction at becomes code in a SpecEmu-style map, which
sna2ctl.py turns into a control file; sna2skool.py then writes the skool file.

Writes OUTDIR/mem.bin, OUTDIR/code.map, OUTDIR/auto.ctl and OUTDIR/cpc.skool.
Code a profile never reached (the docking sequence, the encyclopedia, the
equipment missions in the sessions so far) comes out as data: add `c` lines to
a hand-written control file for it.
"""
import struct
import subprocess
import sys
from pathlib import Path

BIN = Path(sys.executable).parent


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    ram, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    mem = ram.read_bytes()[:65536]
    (out / "mem.bin").write_bytes(mem)
    code = bytearray(65536)
    for cov in sys.argv[3:]:
        counts = struct.unpack("<65536I", Path(cov).read_bytes()[:262144])
        for a, n in enumerate(counts):
            if n:
                code[a] = 1
    (out / "code.map").write_bytes(code)
    print(f"{sum(code)} addresses executed")
    ctl = subprocess.run([str(BIN / "sna2ctl.py"), "-h", "-o", "0", "-m", str(out / "code.map"), str(out / "mem.bin")],
                         capture_output=True, text=True, check=True).stdout
    (out / "auto.ctl").write_text(ctl)
    skool = subprocess.run([str(BIN / "sna2skool.py"), "-H", "-o", "0", "-c", str(out / "auto.ctl"), str(out / "mem.bin")],
                           capture_output=True, text=True, check=True).stdout
    (out / "cpc.skool").write_text(skool)
    print(f"wrote {out / 'cpc.skool'} ({skool.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
