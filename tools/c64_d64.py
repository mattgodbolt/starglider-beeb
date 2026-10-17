#!/usr/bin/env python3
"""List or extract the files on a Commodore 1541 disc image (.d64).

    c64_d64.py IMAGE            list the directory and the BAM's free count
    c64_d64.py IMAGE OUTDIR     extract every file, PRGs with their load address
    c64_d64.py IMAGE --chains   also print each file's track/sector chain

The directory lives on track 18 from sector 1; each file is a chain of
256-byte sectors whose first two bytes are the next track and sector (track 0
ends the chain and the sector byte is then the last used offset). A PRG's
first two data bytes are its load address, little-endian.

Extracted files are named NN-NAME.TYPE (NN = directory order); a PRG is
written without its two-byte header and its load address goes in the index
file OUTDIR/index.txt as well as the listing.
"""
import sys
from pathlib import Path

# Sectors per track for the 35 standard tracks (40-track images extend zone 4).
def sectors_per_track(track):
    if track <= 17:
        return 21
    if track <= 24:
        return 19
    if track <= 30:
        return 18
    return 17


def track_offsets(ntracks):
    offs, pos = {}, 0
    for t in range(1, ntracks + 1):
        offs[t] = pos
        pos += sectors_per_track(t) * 256
    return offs, pos


class D64:
    def __init__(self, data):
        self.data = data
        for nt in (35, 40, 42):
            offs, size = track_offsets(nt)
            if len(data) in (size, size + size // 256):
                self.ntracks, self.offs = nt, offs
                # An image with an error byte per sector carries them at the end.
                self.errors = data[size:] if len(data) > size else None
                break
        else:
            raise ValueError(f"unexpected .d64 size {len(data)}")

    def sector(self, t, s):
        if not 1 <= t <= self.ntracks or not 0 <= s < sectors_per_track(t):
            raise ValueError(f"bad track/sector {t}/{s}")
        o = self.offs[t] + s * 256
        return self.data[o:o + 256]

    def chain(self, t, s, limit=1000):
        """Yield (track, sector, payload) along a file's chain."""
        seen = set()
        while t and limit:
            if (t, s) in seen:
                raise ValueError(f"loop in chain at {t}/{s}")
            seen.add((t, s))
            sec = self.sector(t, s)
            nt, ns = sec[0], sec[1]
            payload = sec[2:] if nt else sec[2:ns + 1]
            yield t, s, payload
            t, s = nt, ns
            limit -= 1

    def read_chain(self, t, s):
        return b"".join(p for _, _, p in self.chain(t, s))

    def bam(self):
        b = self.sector(18, 0)
        name = petscii(b[0x90:0xA0])
        disk_id = petscii(b[0xA2:0xA7])
        free = sum(b[4 + 4 * (t - 1)] for t in range(1, 36) if t != 18)
        return name, disk_id, free, b

    def directory(self):
        for _t, _s, sec in self.chain(18, 1):
            # The payload lost the link bytes: entries are 32 bytes from offset 0
            # of the raw sector, so rebuild with two pad bytes.
            raw = b"\0\0" + sec + b"\0" * (254 - len(sec))
            for i in range(0, 256, 32):
                e = raw[i:i + 32]
                ftype = e[2]
                if ftype == 0:
                    continue
                yield {
                    "type": ftype,
                    "track": e[3],
                    "sector": e[4],
                    "name": petscii(e[5:21]),
                    "blocks": e[30] | e[31] << 8,
                }


TYPES = {0: "DEL", 1: "SEQ", 2: "PRG", 3: "USR", 4: "REL"}


def petscii(b):
    s = bytes(b).split(b"\xa0")[0]
    return "".join(chr(c) if 32 <= c < 127 else f"\\x{c:02x}" for c in s)


def used_sectors(img):
    """Sectors reachable from the directory, plus track 18's chain."""
    used = {(18, 0)}
    used.update((t, s) for t, s, _ in img.chain(18, 1))
    for e in img.directory():
        if e["track"]:
            try:
                used.update((t, s) for t, s, _ in img.chain(e["track"], e["sector"]))
            except ValueError:
                pass
    return used


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_chains = "--chains" in sys.argv
    img = D64(Path(args[0]).read_bytes())
    out = Path(args[1]) if len(args) > 1 else None
    name, disk_id, free, _ = img.bam()
    print(f'disc "{name}" id "{disk_id}", {img.ntracks} tracks, BAM free {free} blocks')
    index = []
    for n, e in enumerate(img.directory()):
        kind = TYPES.get(e["type"] & 7, "?")
        flags = ("" if e["type"] & 0x80 else "*") + ("<" if e["type"] & 0x40 else "")
        line = f'{n:2d} {e["blocks"]:4d} "{e["name"]}" {kind}{flags} start {e["track"]}/{e["sector"]}'
        try:
            body = img.read_chain(e["track"], e["sector"]) if e["track"] else b""
        except ValueError as err:
            print(line, f"  chain error: {err}")
            continue
        if kind == "PRG" and len(body) >= 2:
            load = body[0] | body[1] << 8
            line += f"  load &{load:04X}-&{load + len(body) - 3:04X} ({len(body) - 2} bytes)"
        else:
            line += f"  {len(body)} bytes"
        print(line)
        if show_chains:
            print("    " + " ".join(f"{t}/{s}" for t, s, _ in img.chain(e["track"], e["sector"])))
        index.append(line)
        if out:
            out.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in e["name"]) or "noname"
            fn = out / f"{n:02d}-{safe}.{kind.lower()}"
            fn.write_bytes(body[2:] if kind == "PRG" else body)
    used = used_sectors(img)
    total = sum(sectors_per_track(t) for t in range(1, img.ntracks + 1))
    stray = []
    for t in range(1, img.ntracks + 1):
        for s in range(sectors_per_track(t)):
            if (t, s) not in used and any(img.sector(t, s)):
                stray.append((t, s))
    print(f"{len(used)} of {total} sectors reached from the directory; "
          f"{len(stray)} other sectors hold non-zero data")
    if stray:
        by_track = {}
        for t, s in stray:
            by_track.setdefault(t, []).append(s)
        for t, ss in by_track.items():
            print(f"    track {t:2d}: sectors {','.join(map(str, ss))}")
    if out:
        (out / "index.txt").write_text("\n".join(index) + "\n")


if __name__ == "__main__":
    main()
