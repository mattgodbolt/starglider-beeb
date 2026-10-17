#!/usr/bin/env python3
"""Rebuild the Apple II Starglider's memory as its loader leaves it.

    a2_image.py IMAGE.do OUTDIR

The disc's only DOS 3.3 file, "STARGLIDER" (&0400), uses DOS's RWTS to read
track 15 sectors 15-13 to &4100 and runs it. That second stage reads seven
segments from a table at &42D1 (six bytes each, pointing at three bytes:
first track, sector count, first page; sectors are read from 15 down, the
track stepping down after sector 0) and on a cold start:
  0  T34  32 sectors -> &2000            (HGR page 1)
  1  T32  16 sectors -> &D000 bank 1      (language card, written via &C089)
  2  T31  45 sectors -> &D000-&FCFF bank 2 (written via &C081)
  3  T16  16 sectors -> &6000, then JSR &6000 (the manual word check, patched
                                          out on this image: JMP &6004 = RTS)
  4  T28   1 sector  -> &0700
  5  T27  75 sectors -> &4400-&8EFF
  6  T22  24 sectors -> &0800-&1FFF
  7  T20  32 sectors -> &2000            (HGR page 1 again)
then moves &4400-&A3FF up to &6000-&BFFF, copies &0700-&0736 to &FFA0 and
jumps to &0800 with language card bank 2 switched in (&C083).
The second stage also keeps the hall of fame in track 28 sector 0 (read to
&4400, EORed and copied to &FE00; written back on a warm start).

Writes OUTDIR/main.bin (64K: main RAM below &C000, bank 2 and the upper
language card above &D000, &C000-&CFFF zero), OUTDIR/lc_bank1.bin (&D000-
&DFFF bank 1) and OUTDIR/segments.txt.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a2_disk import DOS33  # noqa: E402


def read_run(img, track, count):
    out, s = bytearray(), 15
    for _ in range(count):
        out += img.sector(track, s)
        s -= 1
        if s < 0:
            s, track = 15, track - 1
    return bytes(out)


def main():
    img = DOS33(Path(sys.argv[1]).read_bytes())
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    stage2 = read_run(img, 15, 3)  # T15 S15, S14, S13 -> &4100

    def at(a):
        return stage2[a - 0x4100]

    main_ram = bytearray(0x10000)
    bank1 = bytearray(0x1000)
    lines = []
    bank = None
    for n in range(8):
        e = 0x42D1 + 6 * n
        ptr = at(e + 2) | at(e + 3) << 8
        track, count, page = at(ptr), at(ptr + 1), at(ptr + 2)
        data = read_run(img, track, count)
        addr = page << 8
        if n == 1:
            bank = 1  # the stage-2 cold path selects bank 1 (&C089) first
        if n == 2:
            bank = 2  # &418C switches to bank 2 (&C081) after entry 1
        if bank == 1 and 0xD000 <= addr < 0xE000:
            bank1[addr - 0xD000:addr - 0xD000 + len(data)] = data[:0x1000 - (addr - 0xD000)]
            where = "bank 1"
        else:
            main_ram[addr:addr + len(data)] = data
            where = "bank 2/main" if addr >= 0xD000 else "main"
        lines.append(f"{n}: T{track} {count} sectors -> &{addr:04X}-&{addr + len(data) - 1:04X} ({where})")
    # &4168: move &4400-&A3FF up to &6000-&BFFF (page by page, top first).
    main_ram[0x6000:0xC000] = bytes(main_ram[0x4400:0xA400])
    lines.append("moved &4400-&A3FF to &6000-&BFFF")
    # &417F: &0700-&0736 -> &FFA0.
    main_ram[0xFFA0:0xFFD7] = main_ram[0x0700:0x0737]
    lines.append("copied &0700-&0736 to &FFA0-&FFD6")
    main_ram[0xC000:0xD000] = bytes(0x1000)
    (out / "main.bin").write_bytes(bytes(main_ram))
    (out / "lc_bank1.bin").write_bytes(bytes(bank1))
    (out / "segments.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
