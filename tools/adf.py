#!/usr/bin/env python3
"""List or extract the files on an AmigaDOS (OFS or FFS) floppy image.

    adf.py IMAGE            list the files
    adf.py IMAGE OUTDIR     extract them, keeping the directory tree
"""
import struct
import sys
from pathlib import Path

BLOCK = 512


def block(data, n):
    return data[n * BLOCK:(n + 1) * BLOCK]


def longs(b):
    return struct.unpack(">128I", b)


def name_of(b):
    n = b[BLOCK - 80]
    return b[BLOCK - 79:BLOCK - 79 + n].decode("latin-1")


def file_data(data, header, ffs):
    out = bytearray()
    size = longs(block(data, header))[BLOCK // 4 - 47]
    hdr = header
    while hdr:
        h = longs(block(data, hdr))
        count = h[2]
        # Data block pointers run backwards from longword 77.
        for i in range(count):
            blk = h[BLOCK // 4 - 51 - i]
            raw = block(data, blk)
            out += raw if ffs else raw[24:24 + struct.unpack_from(">I", raw, 12)[0]]
        hdr = h[BLOCK // 4 - 2]  # the extension block
    return bytes(out[:size])


def walk(data, dirblock, ffs, prefix=""):
    table = longs(block(data, dirblock))[6:6 + 72]
    for head in table:
        while head:
            b = block(data, head)
            sec_type = struct.unpack_from(">i", b, BLOCK - 4)[0]
            name = prefix + name_of(b)
            if sec_type == 2:
                yield name + "/", None
                yield from walk(data, head, ffs, name + "/")
            elif sec_type == -3:
                yield name, file_data(data, head, ffs)
            head = longs(b)[BLOCK // 4 - 4]  # next in the hash chain


def main():
    data = Path(sys.argv[1]).read_bytes()
    if data[:3] != b"DOS":
        sys.exit(f"not an AmigaDOS disc (boot block starts {data[:4]!r})")
    ffs = data[3] & 1
    root = len(data) // BLOCK // 2
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    print(f"{'FFS' if ffs else 'OFS'}, volume {name_of(block(data, root))!r}")
    for path, content in walk(data, root, ffs):
        if content is None:
            print(f"{'<dir>':>8}  {path}")
            if out:
                (out / path).mkdir(parents=True, exist_ok=True)
            continue
        print(f"{len(content):8d}  {path}")
        if out:
            (out / path).parent.mkdir(parents=True, exist_ok=True)
            (out / path).write_bytes(content)


if __name__ == "__main__":
    main()
