#!/usr/bin/env python3
"""Load an Atari ST GEMDOS program (.PRG) and apply its relocation table.

    st_prg.py PRG                 print the header and the relocation summary
    st_prg.py PRG --strings [N]   list printable runs of N+ bytes (default 5)

As a module: `load(path, base=0)` returns a Prg with the text segment
relocated to `base` (0 keeps every address an offset into the text segment,
the convention docs/research/st.md uses), the set of relocated longword
offsets, and the header fields.

The header is 28 bytes: magic &601A, text, data, bss and symbol sizes,
a reserved long, the program flags and the absolute flag. The relocation
table follows text+data+symbols: a longword offset to the first fixup, then
bytes, each a step to the next (1 means step 254 without a fixup, 0 ends).
"""
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Prg:
    raw: bytes
    text_len: int
    data_len: int
    bss_len: int
    sym_len: int
    flags: int
    absflag: int
    image: bytearray            # text + data, relocated to `base`
    base: int
    relocs: list = field(default_factory=list)   # offsets of relocated longs
    reloc_table_len: int = 0

    def u8(self, a):
        return self.image[a - self.base]

    def u16(self, a):
        return struct.unpack_from(">H", self.image, a - self.base)[0]

    def s16(self, a):
        return struct.unpack_from(">h", self.image, a - self.base)[0]

    def u32(self, a):
        return struct.unpack_from(">I", self.image, a - self.base)[0]


def load(path, base=0):
    raw = Path(path).read_bytes()
    magic, tlen, dlen, blen, slen, _res, flags, absflag = struct.unpack_from(">HIIIIIIH", raw, 0)
    if magic != 0x601A:
        raise ValueError(f"not a GEMDOS program (magic {magic:04X})")
    body = bytearray(raw[28:28 + tlen + dlen])
    prg = Prg(raw, tlen, dlen, blen, slen, flags, absflag, body, base)
    if absflag:
        return prg
    p = 28 + tlen + dlen + slen
    first = struct.unpack_from(">I", raw, p)[0]
    p += 4
    if first:
        off = first
        offsets = [off]
        while True:
            b = raw[p]
            p += 1
            if b == 0:
                break
            if b == 1:
                off += 254
                continue
            off += b
            offsets.append(off)
        for o in offsets:
            v = struct.unpack_from(">I", body, o)[0]
            struct.pack_into(">I", body, o, (v + base) & 0xFFFFFFFF)
        prg.relocs = offsets
    prg.reloc_table_len = p - (28 + tlen + dlen + slen)
    return prg


def strings(prg, minlen=5):
    img = prg.image
    out, start = [], None
    for i, b in enumerate(img):
        ok = 0x20 <= b < 0x7F
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if i - start >= minlen:
                out.append((start + prg.base, img[start:i].decode("ascii")))
            start = None
    return out


def main():
    prg = load(sys.argv[1])
    if "--strings" in sys.argv:
        i = sys.argv.index("--strings")
        n = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 5
        for a, s in strings(prg, n):
            print(f"&{a:05X} {s}")
        return
    print(f"text   {prg.text_len:7d}  &{prg.text_len:05X}")
    print(f"data   {prg.data_len:7d}")
    print(f"bss    {prg.bss_len:7d}")
    print(f"syms   {prg.sym_len:7d}")
    print(f"flags  &{prg.flags:08X}  absflag {prg.absflag}")
    print(f"relocs {len(prg.relocs)} fixups, table {prg.reloc_table_len} bytes")
    if prg.relocs:
        print(f"       first &{prg.relocs[0]:05X} last &{prg.relocs[-1]:05X}")


if __name__ == "__main__":
    main()
