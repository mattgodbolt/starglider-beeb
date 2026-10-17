#!/usr/bin/env python3
"""List or extract the files on a FAT12 floppy image (Atari ST .st, PC .img).

    fat12.py IMAGE            list the files
    fat12.py IMAGE OUTDIR     extract them, keeping the directory tree
"""
import struct
import sys
from pathlib import Path


def read_image(path):
    data = Path(path).read_bytes()
    bps, spc, reserved, nfats, ndir, total, _media, spf = struct.unpack_from("<HBHBHHBH", data, 11)
    root = (reserved + nfats * spf) * bps
    first_data = root + ndir * 32
    fat = data[reserved * bps:(reserved + spf) * bps]
    return data, bps * spc, root, ndir, first_data, fat


def fat_next(fat, cluster):
    off = cluster * 3 // 2
    v = fat[off] | fat[off + 1] << 8
    return v >> 4 if cluster & 1 else v & 0xFFF


def chain(data, csize, first_data, fat, cluster, size=None):
    out = bytearray()
    while 2 <= cluster < 0xFF0:
        start = first_data + (cluster - 2) * csize
        out += data[start:start + csize]
        cluster = fat_next(fat, cluster)
    return bytes(out if size is None else out[:size])


def entries(raw):
    for i in range(0, len(raw), 32):
        e = raw[i:i + 32]
        if e[0] == 0:
            break
        if e[0] == 0xE5 or e[11] == 0x0F or e[11] & 0x08:
            continue
        name = e[0:8].decode("latin-1").rstrip()
        ext = e[8:11].decode("latin-1").rstrip()
        if name in (".", ".."):
            continue
        cluster, size = struct.unpack_from("<HI", e, 26)
        yield (name + ("." + ext if ext else "")), e[11], cluster, size


def walk(img, raw, prefix=""):
    data, csize, _root, _ndir, first_data, fat = img
    for name, attr, cluster, size in entries(raw):
        path = prefix + name
        if attr & 0x10:
            yield path + "/", None
            yield from walk(img, chain(data, csize, first_data, fat, cluster), path + "/")
        else:
            yield path, chain(data, csize, first_data, fat, cluster, size)


def main():
    img = read_image(sys.argv[1])
    data, _csize, root, ndir, _first, _fat = img
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    for path, content in walk(img, data[root:root + ndir * 32]):
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
