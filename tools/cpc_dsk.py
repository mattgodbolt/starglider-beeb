#!/usr/bin/env python3
"""Read an Amstrad CPC disc image (.dsk, standard or extended) and its AMSDOS files.

    cpc_dsk.py IMAGE                 list the tracks' formats and the directory
    cpc_dsk.py IMAGE OUTDIR          also extract each file: NAME.EXT is the file
                                     as stored (AMSDOS header included), and
                                     NAME.EXT.bin is its body with the header removed

The listing shows each file's AMSDOS header (type, load and execution
address, length) when the first 128 bytes carry a valid header checksum.
A track or sector that departs from the disc's own format (other sizes, odd
IDs, FDC error flags, short data) is reported, since that is where copy
protection lives.

Supports the DATA format (sectors &C1-&C9, no reserved tracks), the SYSTEM
format (&41-&49, two reserved tracks) and the IBM format (&01-&08, one).
"""
import struct
import sys
from pathlib import Path

FORMATS = {
    # first sector ID: (name, sectors per track, reserved tracks)
    0xC1: ("DATA", 9, 0),
    0x41: ("SYSTEM", 9, 2),
    0x01: ("IBM", 8, 1),
}
BLOCK = 1024
DIR_ENTRIES = 64
FILE_TYPES = {0: "BASIC", 1: "BASIC (protected)", 2: "binary", 3: "binary (protected)",
              0x16: "ASCII"}


class Disc:
    """The sectors of a .dsk image, keyed by (track, side, sector ID)."""

    def __init__(self, path):
        data = Path(path).read_bytes()
        self.extended = data.startswith(b"EXTENDED CPC DSK File")
        if not (self.extended or data.startswith(b"MV - CPC")):
            raise ValueError(f"{path}: not a CPC .dsk image")
        self.creator = data[0x22:0x30].rstrip(b"\0").decode("latin-1")
        self.tracks, self.sides = data[0x30], data[0x31]
        self.sectors = {}
        self.track_info = []
        self.oddities = []
        off = 0x100
        for t in range(self.tracks * self.sides):
            size = data[0x34 + t] * 256 if self.extended else struct.unpack_from("<H", data, 0x32)[0]
            if size == 0:
                self.track_info.append((t // self.sides, t % self.sides, "unformatted", []))
                self.oddities.append(f"track {t // self.sides} side {t % self.sides}: unformatted")
                continue
            ti = data[off:off + size]
            if not ti.startswith(b"Track-Info"):
                raise ValueError(f"track block {t} at {off:#x} has no Track-Info header")
            track, side, nominal, nsec = ti[0x10], ti[0x11], ti[0x14], ti[0x15]
            pos = 0x100
            ids = []
            for s in range(nsec):
                c, h, r, n, st1, st2, length = struct.unpack_from("<BBBBBBH", ti, 0x18 + 8 * s)
                if not self.extended:
                    length = 128 << nominal
                body = ti[pos:pos + length]
                pos += length
                self.sectors[(track, side, r)] = body
                ids.append(r)
                if n != 2 or length != 512 or st1 or st2 or c != track or h != side:
                    self.oddities.append(
                        f"track {track} side {side} sector &{r:02X}: C={c} H={h} N={n} "
                        f"ST1=&{st1:02X} ST2=&{st2:02X} stored length {length}")
            self.track_info.append((track, side, f"{nsec} sectors, N={nominal}, gap &{ti[0x16]:02X}, "
                                                 f"filler &{ti[0x17]:02X}", ids))
            off += size

    def format(self):
        first = min(r for (t, h, r) in self.sectors if t == 0 and h == 0)
        if first not in FORMATS:
            raise ValueError(f"unknown format: track 0's lowest sector ID is &{first:02X}")
        return first, *FORMATS[first]

    def logical_sectors(self):
        """Every 512-byte sector after the reserved tracks, in AMSDOS's order."""
        first, _name, spt, reserved = self.format()
        out = []
        for t in range(reserved, self.tracks):
            for r in range(first, first + spt):
                out.append(self.sectors.get((t, 0, r), b"\xE5" * 512))
        return out

    def block(self, n):
        secs = self.logical_sectors()
        return b"".join(secs[n * 2:n * 2 + 2])


def directory(disc):
    """The AMSDOS directory's extents, grouped into files: {(user, name): [extent...]}."""
    raw = disc.block(0) + disc.block(1)
    files = {}
    for i in range(DIR_ENTRIES):
        e = raw[i * 32:i * 32 + 32]
        user = e[0]
        if user == 0xE5:
            continue
        name = bytes(b & 0x7F for b in e[1:9]).decode("latin-1").rstrip()
        ext = bytes(b & 0x7F for b in e[9:12]).decode("latin-1").rstrip()
        attrs = ("R" if e[9] & 0x80 else "") + ("S" if e[10] & 0x80 else "")
        extent, records = e[12], e[15]
        blocks = [b for b in e[16:32] if b]
        files.setdefault((user, f"{name}.{ext}" if ext else name), []).append(
            (extent, records, blocks, attrs))
    return files


def file_bytes(disc, extents):
    out = bytearray()
    for _extent, records, blocks, _attrs in sorted(extents):
        chunk = b"".join(disc.block(b) for b in blocks)
        out += chunk[:records * 128]
    return bytes(out)


def amsdos_header(data):
    """The AMSDOS header's fields, or None if the first 128 bytes don't checksum as one."""
    if len(data) < 128:
        return None
    if sum(data[:67]) & 0xFFFF != struct.unpack_from("<H", data, 67)[0]:
        return None
    return {
        "user": data[0],
        "name": data[1:9].decode("latin-1").rstrip() + "." + data[9:12].decode("latin-1").rstrip(),
        "type": data[0x12],
        "load": struct.unpack_from("<H", data, 0x15)[0],
        "length": struct.unpack_from("<H", data, 0x18)[0],
        "exec": struct.unpack_from("<H", data, 0x1A)[0],
        "length24": data[0x40] | data[0x41] << 8 | data[0x42] << 16,
    }


def main():
    disc = Disc(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    first, fmt, spt, reserved = disc.format()
    print(f"{'extended' if disc.extended else 'standard'} DSK by {disc.creator!r}: "
          f"{disc.tracks} tracks, {disc.sides} side(s); {fmt} format "
          f"(sectors &{first:02X}-&{first + spt - 1:02X}, {reserved} reserved tracks)")
    layouts = {}
    for track, side, desc, ids in disc.track_info:
        key = (desc, tuple(ids))
        layouts.setdefault(key, []).append(track)
    for (desc, ids), tracks in layouts.items():
        print(f"  tracks {tracks[0]}-{tracks[-1]} ({len(tracks)}): {desc}; IDs "
              + " ".join(f"{r:02X}" for r in ids))
    print("  oddities:", "none" if not disc.oddities else "")
    for o in disc.oddities:
        print("   ", o)
    print()
    print(f"{'user':>4} {'name':12} {'attr':4} {'stored':>7} {'type':18} {'load':>5} {'exec':>5} {'length':>6}  blocks")
    if out:
        out.mkdir(parents=True, exist_ok=True)
    for (user, name), extents in sorted(directory(disc).items()):
        data = file_bytes(disc, extents)
        hdr = amsdos_header(data)
        blocks = [b for e in sorted(extents) for b in e[2]]
        attrs = extents[0][3]
        if hdr:
            body = data[128:128 + hdr["length24"]]
            kind = FILE_TYPES.get(hdr["type"], f"type &{hdr['type']:02X}")
            print(f"{user:4d} {name:12} {attrs:4} {len(data):7d} {kind:18} &{hdr['load']:04X} "
                  f"&{hdr['exec']:04X} {hdr['length24']:6d}  {blocks[0]}-{blocks[-1]}")
        else:
            body = data
            print(f"{user:4d} {name:12} {attrs:4} {len(data):7d} {'(no header)':18} {'':>5} {'':>5} "
                  f"{'':>6}  {blocks[0]}-{blocks[-1]}")
        if out:
            (out / name).write_bytes(data)
            (out / (name + ".bin")).write_bytes(body)


if __name__ == "__main__":
    main()
