#!/usr/bin/env python3
"""What the disc's title song should do (decision 5), for
tools/songcheck.mjs: tools/mksong.py's zx_bass conversion of the Spectrum
128K's capture, tick by tick, a pass and LOOP ticks more, as the Spectrum
loops it; and the same with channel A's low notes taken up octaves, as
the end screen's bands leave it no timer (decision 58).

    songmodel.py CAPTURE.json OUT.json

Each tick's record (mksong.py's convert's, flattened): the AY's registers
0-13; 1 if register 13 was written; the SN's three tone periods and four
attenuations as last written (a bass channel's attenuation is its edges');
the noise's control and how many times the tick wrote it; each channel's
bass half-cycle in microseconds (0 for none) and its attenuation. Then the
pass's bass edges, from the conversion's own writes: for each bass
channel, how many in the pass.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mksong  # noqa: E402

LOOP = 2000                             # ticks past the pass (zx_song.py's CHECK)
BANDS = 6000                            # ticks with channel A's octaves


def flat(r):
    return (r["ay"] + [int(r["env"])] + [-1 if p is None else p for p in r["tone"]]
            + [-1 if a is None else a for a in r["att"]] + [-1 if r["noise"] is None else r["noise"], r["noise_w"]]
            + r["half"] + [-1 if h is None else h for h in r["held"]])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("capture")
    ap.add_argument("out")
    args = ap.parse_args()
    cap = json.loads(Path(args.capture).read_text())
    length = cap["length"]
    records = []
    _, _, _, tick_s = mksong.convert(cap, True, length + LOOP, records)
    _, _, edges, _ = mksong.convert(cap, True)
    bands = []
    mksong.convert(cap, (False, True, True), BANDS, bands)
    out = {
        "length": length, "loop": LOOP, "tick_us": tick_s * 1e6, "edges": edges,
        "fields": ["ay"] * 14 + ["env", "tone0", "tone1", "tone2", "att0", "att1", "att2", "att3", "noise", "noise_w",
                                 "half0", "half1", "half2", "held0", "held1", "held2"],
        "records": [flat(r) for r in records],
        "bands": [flat(r) for r in bands],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out) + "\n")
    print(f"songmodel: {len(records)} ticks ({length} a pass), {edges} bass edges; "
          f"{len(bands)} with channel A's octaves -> {args.out}")


if __name__ == "__main__":
    main()
