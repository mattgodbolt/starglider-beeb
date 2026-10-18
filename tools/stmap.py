#!/usr/bin/env python3
"""The map between the ST's logic state and the port's, for the harness
(tools/logicrun.mjs): every variable whose declaration carries {ST address
kind} (src/vars.6502 says the forms), and every object field
(build/gen/objects.json), with the port's address of it and where the
ST's is in tools/st_steps.py's regions.

    stmap.py SYMBOLS [OBJECTS.json]     the map, as JSON, to stdout

A port address in &8000-&8FFF is ANDY's.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_steps  # noqa: E402

SRC = Path(__file__).resolve().parent.parent / "src"
DECL = re.compile(r"^\s*\.?(\w+)\s+(?:SKIP\s+\S+|=\s*[^;\\]+?)\s*[;\\].*?\{ST\s+([^}]+)\}")
SIZES = {"byte": 1, "word8": 1, "word": 2, "long": 4, "slot": 1}
OBJECTS_AT = 0x129A                     # in the variable block
RECORD = 64


def symbols(path):
    out = {}
    for assembly in json.loads(Path(path).read_text())["assemblies"]:
        for section in assembly["sections"]:
            for kind in section.values():
                if isinstance(kind, dict):
                    for k, v in kind.items():
                        if isinstance(v, dict) and "value" in v and "@" not in k:
                            out[k] = v["value"]
    return out


def st_place(addr):
    """(region, offset) of an ST address in the capture's regions."""
    a = addr.strip()
    if m := re.fullmatch(r"\$([0-9A-Fa-f]+)\(a6\)", a):
        ea = st_steps.A6 + int(m.group(1), 16)
    elif m := re.fullmatch(r"P&([0-9A-Fa-f]+)", a):
        ea = st_steps.BASE + int(m.group(1), 16)
    elif m := re.fullmatch(r"&([0-9A-Fa-f]+)", a):
        ea = int(m.group(1), 16)
    else:
        raise ValueError(f"no such ST address: {addr}")
    for name, start, n in st_steps.REGIONS:
        if start <= ea < start + n:
            return name, ea - start
    raise ValueError(f"{addr} isn't in any of the capture's regions (tools/st_steps.py)")


def variables(syms):
    out = []
    for path in sorted(SRC.rglob("*.6502")):
        for line in path.read_text().splitlines():
            m = DECL.match(line)
            if not m:
                continue
            name, spec = m.group(1), m.group(2).split()
            if name not in syms:
                raise SystemExit(f"{path}: {name} isn't in the build's symbols")
            given = spec[-1] == "in"
            if given:
                spec = spec[:-1]
            addr, kind, args = spec[0], spec[1], [int(x) for x in spec[2:]]
            region, offset = st_place(addr)
            e = {"name": name, "at": syms[name], "kind": kind, "region": region, "offset": offset}
            if given:
                e["input"] = True
            if kind == "raw":
                e["count"] = args[0]
            elif kind in ("wlo", "whi", "barr"):
                e["count"], e["stride"] = args
            elif kind in ("slots", "slotsdown"):
                e["count"] = args[0]
            elif kind not in SIZES:
                raise SystemExit(f"{path}: {name}: no such kind {kind}")
            out.append(e)
    return out


def objects(syms, layout):
    out = []
    for f in json.loads(Path(layout).read_text())["fields"]:
        if f["st"] is None:
            continue
        out.append({"name": f"ob_{f['name']}", "kind": f["kind"], "at": [syms[a] for a in f["arrays"]],
                    "field": f["st"], "slots": 140 + 2})
    return out


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    syms = symbols(sys.argv[1])
    layout = sys.argv[2] if len(sys.argv) == 3 else "build/gen/objects.json"
    json.dump({"variables": variables(syms), "objects": objects(syms, layout),
               "records": {"region": "vars", "offset": OBJECTS_AT, "size": RECORD,
                           "silo": {"region": "silo", "offset": 0}}}, sys.stdout)


if __name__ == "__main__":
    main()
