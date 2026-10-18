#!/usr/bin/env python3
"""Check the port's sine table (src/sine.6502, built by baron) against the
ST's own (&13D6C in STAR.PRG), entry for entry.

    sinecheck.py PRG SINE          SINE: the assembled bank (sine_lo, sine_hi)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

ST_SINE = 0x13D6C


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    prg = st_prg.load(sys.argv[1])
    data = Path(sys.argv[2]).read_bytes()
    n = len(data) // 2
    bad = [i for i in range(n) if (data[i] | data[n + i] << 8) != prg.u16(ST_SINE + 2 * i)]
    print(f"sine: {n} entries, {len(bad)} differ from the ST's" + (f": {bad[:10]}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
