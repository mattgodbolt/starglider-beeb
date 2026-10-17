#!/usr/bin/env python3
"""Rebuild the C64 Starglider's running memory from the cracked disc's two files.

    c64_unfreeze.py IMAGE.d64 OUTDIR

The disc holds a freezer-cartridge backup, not Rainbird's files:
  - "STARGLIDER" (load &02C0) autostarts, copies its own &0900-&68FF up to
    &A000-&FFFF, then loads "STAR+" at &0801 and runs it.
  - "STAR+" moves &0D50-&CEF9 up to &3E56-&FFFF, restores colour RAM from
    &0900, the stack page from &0C00, zero page from &0B00, the VIC from &0D00
    and the CIAs from &0D30/&0D40, then jumps to a decruncher in zero page.
This runs both stubs and the decruncher on py65 with the C64's banking modelled
(the &01 port picks RAM, I/O or ROM; ROM reads return 0 and are counted), and
stops at the freezer's resume code. It writes:
  OUTDIR/ram.bin      the 64K RAM as the game sees it on resume
  OUTDIR/io.txt       the VIC, SID and CIA register writes, the last of each
  OUTDIR/colour.bin   colour RAM (1000 nybbles, one per byte)
  OUTDIR/resume.txt   where the freezer resumes the game (registers, PC)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c64_d64 import D64  # noqa: E402
from py65.devices.mpu6502 import MPU  # noqa: E402


class C64Mem:
    """RAM with the 6510 port at &00/&01 choosing what &A000-&FFFF shows."""

    def __init__(self):
        self.ram = bytearray(0x10000)
        self.ram[1] = 0x37
        self.io = {}
        self.colour = bytearray(1024)
        self.rom_reads = 0
        self.trace_io = []

    def _cfg(self):
        p = self.ram[1] & 7
        loram, hiram, charen = p & 1, p & 2, p & 4
        basic = loram and hiram
        kernal = hiram
        io = (loram or hiram) and charen
        chars = (loram or hiram) and not charen
        return basic, kernal, io, chars

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(0x10000))]
        basic, kernal, io, chars = self._cfg()
        if 0xA000 <= a < 0xC000 and basic:
            self.rom_reads += 1
            return 0
        if a >= 0xE000 and kernal:
            self.rom_reads += 1
            return 0
        if 0xD000 <= a < 0xE000:
            if io:
                if 0xD800 <= a < 0xDC00:
                    return self.colour[a - 0xD800] | 0xF0
                return self.io.get(a, 0)
            if chars:
                self.rom_reads += 1
                return 0
        return self.ram[a]

    def __setitem__(self, a, v):
        _basic, _kernal, io, _chars = self._cfg()
        if 0xD000 <= a < 0xE000 and io:
            if 0xD800 <= a < 0xDC00:
                self.colour[a - 0xD800] = v & 15
            else:
                self.io[a] = v
                self.trace_io.append((a, v))
            return
        self.ram[a] = v


def find(img, name):
    for e in img.directory():
        if e["name"] == name:
            body = img.read_chain(e["track"], e["sector"])
            return body[0] | body[1] << 8, body[2:]
    raise KeyError(name)


def unfreeze(d64_path, mem=None):
    """Run the backup's stubs; return (mem, mpu, steps) at the game's resume point."""
    img = D64(Path(d64_path).read_bytes())
    mem = mem or C64Mem()
    a1, front = find(img, "STARGLIDER")
    a2, game = find(img, "STAR+")
    mem.ram[a1:a1 + len(front)] = front
    # STARGLIDER's stub at &080D: with RAM banked in, copy &0900-&68FF to &A000.
    mem.ram[0xA000:0x10000] = mem.ram[0x0900:0x6900]
    # ...then the KERNAL loads STAR+ at &0801 and the stub "returns" to &080D.
    mem.ram[a2:a2 + len(game)] = game
    mpu = MPU(memory=mem, pc=0x080D)
    mpu.sp = 0xFF
    steps = 0
    seen_zp = False
    while steps < 50_000_000:
        pc = mpu.pc
        if pc < 0x100:
            seen_zp = True
        # The resume code runs from the stack page once the decruncher is done;
        # it puts back zero page &50-&FF, sets &01 and RTIs into the game.
        if seen_zp and pc >= 0x200:
            break
        mpu.step()
        steps += 1
    return mem, mpu, steps


def main():
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    mem, mpu, steps = unfreeze(sys.argv[1])
    resume_pc = mpu.pc
    (out / "ram.bin").write_bytes(bytes(mem.ram))
    (out / "colour.bin").write_bytes(bytes(mem.colour[:1000]))
    last = {}
    for a, v in mem.trace_io:
        last[a] = v
    lines = [f"&{a:04X} = &{v:02X}" for a, v in sorted(last.items())]
    (out / "io.txt").write_text("\n".join(lines) + "\n")
    regs = (f"stopped at PC &{resume_pc:04X} after {steps} instructions, "
            f"{mpu.processorCycles} cycles; A=&{mpu.a:02X} X=&{mpu.x:02X} Y=&{mpu.y:02X} "
            f"SP=&{mpu.sp:02X} P=&{mpu.p:02X}; &01=&{mem.ram[1]:02X}; ROM reads {mem.rom_reads}")
    (out / "resume.txt").write_text(regs + "\n")
    print(regs)
    for k in (0xD011, 0xD016, 0xD018, 0xD020, 0xD021, 0xDD00, 0xDD02):
        if k in last:
            print(f"  &{k:04X} = &{last[k]:02X}")


if __name__ == "__main__":
    main()
