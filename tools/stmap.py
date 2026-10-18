#!/usr/bin/env python3
"""The map between the ST's logic state and the port's, for the harness
(tools/logicrun.mjs): every variable whose declaration carries {ST address
kind} (src/vars.6502 says the forms), and every object field
(build/gen/objects.json), with the port's address of it and where the
ST's is in tools/st_steps.py's regions.

    stmap.py SYMBOLS [OBJECTS.json]     the map, as JSON, to stdout

A port address in &8000-&8FFF is ANDY's. Two declarations of one ST
variable are refused, but for a deliberate copy, marked `also` after the
kind.
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


def st_bytes(e):
    """The ST's bytes a variable holds, as (region, offset)s."""
    r, o, k = e["region"], e["offset"], e["kind"]
    if k in ("wlo", "whi", "barr"):
        lo = 1 if k == "wlo" else 0
        return [(r, o + i * e["stride"] + lo) for i in range(e["count"])]
    n = {"byte": 1, "word8": 2, "word": 2, "long": 4, "slot": 4, "index": 4, "list": 4}.get(k)
    if k == "raw":
        n = e["count"]
    elif k == "slots":
        n = 4 * e["count"]
    return [(r, o + i) for i in range(n)]


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
            # flags last: "also", a second copy of the ST's variable on
            # purpose; "in", an input the outside world writes at any moment
            # (the ST's interrupts), put but never compared
            also = given = False
            while spec[-1] in ("also", "in"):
                also, given = also or spec[-1] == "also", given or spec[-1] == "in"
                spec = spec[:-1]
            addr, kind = spec[0], spec[1]
            region, offset = st_place(addr)
            e = {"name": name, "at": syms[name], "kind": kind, "region": region, "offset": offset, "also": also,
                 "where": str(path.relative_to(SRC.parent))}
            if given:
                e["input"] = True
            if kind == "index":
                # (the array's own ST address, then its entries' size)
                e["base"], e["stride"] = int(spec[2].lstrip("&"), 16), int(spec[3])
                out.append(e)
                continue
            if kind == "list":
                # list COUNT N: the ST's pointer to a list's first entry
                # (record pointers, pushed downward), its count's ST
                # address, and the port's count of it (slots, in the
                # order pushed)
                e["count_region"], e["count_offset"] = st_place(spec[2])
                if spec[3] not in syms:
                    raise SystemExit(f"{path}: {name}: {spec[3]} isn't in the build's symbols")
                e["count_at"] = syms[spec[3]]
                out.append(e)
                continue
            args = [int(x) for x in spec[2:]]
            if kind == "raw":
                e["count"] = args[0]
            elif kind in ("wlo", "whi", "barr"):
                e["count"], e["stride"] = args
            elif kind == "slots":
                e["count"] = args[0]
            elif kind not in SIZES:
                raise SystemExit(f"{path}: {name}: no such kind {kind}")
            out.append(e)
    # One port variable for each of the ST's bytes: two would each be put
    # from the ST's state, and pass, while the code that writes one never
    # feeds the code that reads the other. A copy marked `also` is one on
    # purpose.
    owner, clashes = {}, []
    for e in out:
        if e["also"]:
            continue
        for byte in st_bytes(e):
            o = owner.setdefault(byte, e)
            if o is not e and (o["name"], e["name"]) not in clashes:
                clashes.append((o["name"], e["name"]))
    if clashes:
        raise SystemExit("one ST variable, two port variables (keep one, or mark a deliberate copy `also`): " +
                         ", ".join(f"{x} and {y}" for x, y in clashes))
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
