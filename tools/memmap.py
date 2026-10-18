#!/usr/bin/env python3
"""What each region of the memory map (src/memory.6502) holds, from a
build's symbols: each section's start, its guard (its budget) and what it
uses.

    memmap.py [SYMBOLS]     the disc's by default (build/starglider.json)

A section that saves bytes has its size; a virtual one (the workspace,
the lists, the objects) is reckoned up to its last label, which leaves out
that label's own length, so its use is a byte or so short.
"""
import json
import sys
from pathlib import Path


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "build/starglider.json")
    data = json.loads(path.read_text())
    rows = []
    zp_top = 0
    for assembly in data["assemblies"]:
        for sec in assembly["sections"]:
            for v in (sec.get("za_autos") or {}).values():
                zp_top = max(zp_top, v["value"])
            name, attrs = sec.get("name"), sec.get("attributes") or {}
            if not name or "org" not in attrs:
                continue
            org, guard = attrs["org"], attrs.get("guard")
            if attrs.get("virtual"):
                labels = [v["value"] for v in (sec.get("labels") or {}).values()]
                used = (max(labels) - org + 1) if labels else 0
            else:
                used = sec["size"]
            rows.append((name, org, guard, used))
    print(f"{'Region':<12} {'From':>6} {'Guard':>6} {'Used':>6} {'Free':>6}")
    for name, org, guard, used in rows:
        free = "" if guard is None else f"{guard - org - used:6}"
        print(f"{name:<12} {org:6X} {guard or 0:6X} {used:6} {free}")
    print(f"{'ZP pool':<12} {0x20:6X} {0xFC:6X} {'':>6} {'':>6}  baron's highest allocation &{zp_top:02X}")


if __name__ == "__main__":
    main()
