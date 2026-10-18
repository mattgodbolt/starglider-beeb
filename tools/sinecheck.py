#!/usr/bin/env python3
"""Check the port's sine table (src/sine.6502, built by baron) against the
ST's own (&13D6C in STAR.PRG), entry for entry.

    sinecheck.py PRG SINE SYMBOLS   SINE: the assembled bank, loaded at &8000;
                                    SYMBOLS: the build's, for sine_lo, sine_hi
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

ST_SINE = 0x13D6C


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    prg = st_prg.load(sys.argv[1])
    data = Path(sys.argv[2]).read_bytes()
    syms = {}
    for assembly in json.loads(Path(sys.argv[3]).read_text())["assemblies"]:
        for section in assembly["sections"]:
            for kind in ("labels", "assignments"):
                for k, v in (section.get(kind) or {}).items():
                    syms[k] = v["value"]
    lo, hi, n = syms["sine_lo"] - 0x8000, syms["sine_hi"] - 0x8000, syms["SINE_ENTRIES"]
    bad = [i for i in range(n) if (data[lo + i] | data[hi + i] << 8) != prg.u16(ST_SINE + 2 * i)]
    print(f"sine: {n} entries, {len(bad)} differ from the ST's" + (f": {bad[:10]}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
