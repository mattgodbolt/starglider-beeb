#!/usr/bin/env python3
"""List or extract an Apple II DOS 3.3 disc image (.do/.dsk in DOS order).

    a2_disk.py IMAGE              list the VTOC, the catalog and a sector map
    a2_disk.py IMAGE OUTDIR       also extract every file
    a2_disk.py IMAGE --sector T S hex-dump one logical sector

The VTOC is track 17 sector 0; the catalog is a chain of sectors from the
VTOC's pointer, seven 35-byte entries each (first T/S list track and sector,
type, 30-byte name, length in sectors). Each file's track/sector list holds
122 T/S pairs and links to the next list. A binary (B) file starts with its
load address and length (two words), which the listing shows.

Extracted files are named NN-NAME.T (T = the type letter); B files are
written without their four-byte header, and OUTDIR/index.txt records where
each loads. The map marks each sector: digit/letter = file number in catalog
order, V = VTOC, C = catalog, B = boot (track 0), . = all zero, ? = data
reached by no file.
"""
import sys
from pathlib import Path

TYPES = {0x00: "T", 0x01: "I", 0x02: "A", 0x04: "B", 0x08: "S", 0x10: "R", 0x20: "a", 0x40: "b"}


class DOS33:
    def __init__(self, data):
        if len(data) != 35 * 16 * 256:
            raise ValueError(f"unexpected image size {len(data)}")
        self.data = data

    def sector(self, t, s):
        o = (t * 16 + s) * 256
        return self.data[o:o + 256]

    def vtoc(self):
        v = self.sector(17, 0)
        return {
            "cat_track": v[1], "cat_sector": v[2], "dos": v[3], "volume": v[6],
            "pairs": v[0x27], "last_track": v[0x30], "direction": v[0x31],
            "tracks": v[0x34], "sectors": v[0x35], "bytes": v[0x36] | v[0x37] << 8,
            "free": [(v[0x38 + 4 * t] << 8 | v[0x39 + 4 * t]) for t in range(35)],
        }

    def catalog(self):
        v = self.vtoc()
        t, s = v["cat_track"], v["cat_sector"]
        seen = set()
        chain = []
        while t and (t, s) not in seen and t < 35 and s < 16:
            seen.add((t, s))
            chain.append((t, s))
            sec = self.sector(t, s)
            for i in range(7):
                e = sec[0x0B + 35 * i:0x0B + 35 * (i + 1)]
                if e[0] in (0, 0xFF):
                    continue
                name = "".join(chr(c & 0x7F) for c in e[3:33]).rstrip()
                yield {
                    "ts_track": e[0], "ts_sector": e[1], "type": e[2] & 0x7F,
                    "locked": bool(e[2] & 0x80), "name": name,
                    "length": e[33] | e[34] << 8, "cat": (t, s),
                }
            t, s = sec[1], sec[2]
        self.cat_chain = chain

    def file_sectors(self, t, s):
        lists, data = [], []
        seen = set()
        while t and (t, s) not in seen and t < 35 and s < 16:
            seen.add((t, s))
            lists.append((t, s))
            sec = self.sector(t, s)
            for i in range(122):
                dt, ds = sec[0x0C + 2 * i], sec[0x0D + 2 * i]
                if dt == 0 and ds == 0:
                    data.append(None)  # a hole, or the end
                else:
                    data.append((dt, ds))
            t, s = sec[1], sec[2]
        while data and data[-1] is None:
            data.pop()
        return lists, data

    def read_file(self, t, s):
        lists, sectors = self.file_sectors(t, s)
        body = b"".join(self.sector(*ts) if ts else bytes(256) for ts in sectors)
        return lists, sectors, body


def hexdump(b, base=0):
    for i in range(0, len(b), 16):
        row = b[i:i + 16]
        txt = "".join(chr(c & 0x7F) if 32 <= (c & 0x7F) < 127 else "." for c in row)
        print(f"{base + i:04X}: {row.hex(' ')}  {txt}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    img = DOS33(Path(args[0]).read_bytes())
    if "--sector" in sys.argv:
        t, s = int(args[1]), int(args[2])
        hexdump(img.sector(t, s))
        return
    out = Path(args[1]) if len(args) > 1 else None
    v = img.vtoc()
    print(f"VTOC: catalog at T{v['cat_track']} S{v['cat_sector']}, DOS {v['dos']}, volume {v['volume']}, "
          f"{v['tracks']} tracks x {v['sectors']} sectors x {v['bytes']} bytes, "
          f"free sectors {sum(bin(f).count('1') for f in v['free'])}")
    owner = {}
    for s in range(16):
        owner[(0, s)] = "B"
    owner[(17, 0)] = "V"
    index = []
    files = list(img.catalog())
    for (t, s) in getattr(img, "cat_chain", []):
        owner[(t, s)] = "C"
    marks = "0123456789abcdefghijklmnopqrstuvwxyz"
    for n, f in enumerate(files):
        lists, sectors, body = img.read_file(f["ts_track"], f["ts_sector"])
        mark = marks[n % len(marks)]
        for ts in lists + [x for x in sectors if x]:
            owner[ts] = mark
        kind = TYPES.get(f["type"], "?")
        line = (f"{mark} {kind}{'*' if f['locked'] else ' '} {f['length']:3d} \"{f['name']}\" "
                f"T/S list T{f['ts_track']} S{f['ts_sector']}, {len(sectors)} data sectors")
        payload = body
        if kind == "B" and len(body) >= 4:
            addr = body[0] | body[1] << 8
            length = body[2] | body[3] << 8
            line += f", load &{addr:04X} length &{length:04X} (to &{addr + length - 1:04X})"
            payload = body[4:4 + length]
        elif kind in "AI" and len(body) >= 2:
            length = body[0] | body[1] << 8
            line += f", program length &{length:04X}"
            payload = body[2:2 + length]
        print(line)
        index.append(line)
        if out:
            out.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in f["name"]) or "noname"
            (out / f"{n:02d}-{safe}.{kind}").write_bytes(payload)
    print("\nsector map (rows = tracks 0-34, columns = sectors 0-F):")
    stray = 0
    for t in range(35):
        row = ""
        for s in range(16):
            if (t, s) in owner:
                row += owner[(t, s)]
            elif not any(img.sector(t, s)):
                row += "."
            else:
                row += "?"
                stray += 1
        print(f"  T{t:02d} {row}")
    print(f"{stray} sectors hold data no file reaches")
    if out:
        (out / "index.txt").write_text("\n".join(index) + "\n")


if __name__ == "__main__":
    main()
