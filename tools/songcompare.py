#!/usr/bin/env python3
"""The title song as the disc plays it against tools/mksong.py's model of
it (decision 5): two WAVs from tools/songwav.mjs, the disc's (from
tools/songcheck.mjs's build/tune/disc.json) and the model's
(build/song/wav/zx_bass_chip.wav, what Matt chose by ear), compared as
song.md compares the candidates with the AY's own: their spectra every
FRAME seconds in BANDS bands from LOW to HIGH Hz, each frame's correlation,
and how loud each is, after the best alignment within SHIFT.

    songcompare.py DISC.wav MODEL.wav [--min CORRELATION]

Exits non-zero if the frames' mean correlation is under --min.
"""
import argparse
import sys
import wave

import numpy as np

FRAME = 0.05
BANDS = 48
LOW, HIGH = 50, 8000
SHIFT = 0.02                            # seconds either way


def load(path):
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 1
        rate = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768
    return x, rate


def spectra(x, rate):
    n = int(FRAME * rate)
    frames = len(x) // n
    edges = np.geomspace(LOW, HIGH, BANDS + 1)
    f = np.fft.rfftfreq(n, 1 / rate)
    which = np.digitize(f, edges) - 1
    win = np.hanning(n)
    out = np.zeros((frames, BANDS))
    for i in range(frames):
        p = np.abs(np.fft.rfft(x[i * n:(i + 1) * n] * win)) ** 2
        for b in range(BANDS):
            sel = which == b
            if sel.any():
                out[i, b] = p[sel].sum()
    return np.log10(out + 1e-12)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("disc")
    ap.add_argument("model")
    ap.add_argument("--min", type=float, default=0.0)
    args = ap.parse_args()
    a, rate = load(args.disc)
    b, rate_b = load(args.model)
    assert rate == rate_b
    # the best alignment: the disc's first tick is its t = 0, the model's
    # first tick its own
    m = min(len(a), len(b)) - int(2 * SHIFT * rate)
    s = int(SHIFT * rate)
    seg = b[s:s + int(10 * rate)]
    best = max(range(-s, s + 1, 4), key=lambda k: float(np.dot(a[s + k:s + k + len(seg)], seg)))
    a = a[max(0, best):]
    b = b[max(0, -best):]
    m = min(len(a), len(b))
    a, b = a[:m], b[:m]
    sa, sb = spectra(a, rate), spectra(b, rate)
    corr = []
    for i in range(len(sa)):
        x, y = sa[i] - sa[i].mean(), sb[i] - sb[i].mean()
        d = np.sqrt((x * x).sum() * (y * y).sum())
        if d > 0:
            corr.append(float((x * y).sum() / d))
    corr = np.array(corr)
    rms = lambda v: 20 * np.log10(np.sqrt(np.mean(v * v)))      # noqa: E731
    print(f"songcompare: {m / rate:.2f} s, aligned {best / rate * 1e3:+.2f} ms; spectra every {FRAME * 1e3:.0f} ms in "
          f"{BANDS} bands {LOW}-{HIGH} Hz correlate {corr.mean():.4f} on average, {np.percentile(corr, 1):.4f} at "
          f"the 1st percentile, {corr.min():.4f} at worst; RMS {rms(a):.2f} dB against {rms(b):.2f} (each at its "
          f"peak), the difference {rms(a - b):.2f} dB")
    if corr.mean() < args.min:
        print(f"songcompare: the mean correlation {corr.mean():.4f} is under {args.min}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
