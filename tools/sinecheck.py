#!/usr/bin/env python3
"""Check the port's sincos (render.6502, from sine.6502's compact table)
against the ST's sine table (&13D6C in STAR.PRG) at every angle: the sine
at each of the 4096 and the cosine, the entry 1024 on.

    sinecheck.py PRG [BUILD]    BUILD: the spike's build (build/spike)

tools/sinerun.mjs runs the spike's spike_sines in jsbeeb, which calls
sincos for each angle and leaves the results in the log's bank.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

ST_SINE = 0x13D6C


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    prg = st_prg.load(sys.argv[1])
    build = sys.argv[2] if len(sys.argv) == 3 else "build/spike"
    here = Path(__file__).resolve().parent
    out = subprocess.run(["node", str(here / "sinerun.mjs"), build], check=True, capture_output=True, text=True)
    got = json.loads(out.stdout.strip().splitlines()[-1])
    st = [prg.u16(ST_SINE + 2 * i) for i in range(5120)]
    bad = [i for i in range(4096) if got[i] != [st[i], st[i + 1024]]]
    print(f"sincos: 4096 angles, {len(bad)} differ from the ST's table" + (f": {bad[:10]}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
