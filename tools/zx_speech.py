#!/usr/bin/env python3
"""Time and extract Starglider 128's speech, with the Spectrum original's own player.

    .venv/bin/python tools/zx_speech.py [--snap build/zx128.z80] [--out build/zx]

The speech player is at &8BEF (A = phrase). Its table at &8C92 has six
bytes a phrase: start, length, delay count, bank. Each sample is a signed
byte; the player halves it, adds &40 and looks it up in three 256-byte
tables at &8200, &8300 and &8400, which give the AY's channel A, B and C
volumes (registers 8, 9, 10), with every tone and noise off so that the
volumes act as a DAC.

For each phrase this calls &8BEF from a stub (on the contended simulator,
interrupts off as the game has them) and logs the AY writes, giving the
sample rate the player achieves. It then writes the phrase as a 16-bit WAV
at that rate, from the samples through the game's volume tables and a
measured AY volume curve. The WAVs are Rainbird's recordings: they go in
build/, which is not committed.
"""
import argparse
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zx import Spectrum, run_script  # noqa: E402
from skoolkit.simutils import PC, T  # noqa: E402

PLAYER = 0x8BEF
TABLE = 0x8C92
N_PHRASES = 4
STUB = 0x4A40
CLOCK128 = 3546900

# The AY-3-8912's output for volumes 0-15, relative to 15 (the levels most
# emulators use, from measurements of the chip).
AY_LEVELS = [0.0, 0.0137, 0.0205, 0.0291, 0.0423, 0.0618, 0.0847, 0.1369,
             0.1691, 0.2647, 0.3527, 0.4499, 0.5704, 0.6873, 0.8482, 1.0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/zx128.z80")
    ap.add_argument("--pre", default="f50,ENTER:tap,f100", help="zx.py steps that get the game flying")
    ap.add_argument("--out", default="build/zx")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = Spectrum(args.snap)
    run_script(base, args.pre, "shots/zx_")
    snap = str(out / ".zx_speech_base.z80")
    base.save(snap)
    mem = base.mem
    vol = [[mem[0x8200 + 0x100 * c + i] for i in range(256)] for c in range(3)]
    total_bytes = 0
    try:
        for n in range(N_PHRASES):
            e = TABLE + 6 * n
            start = mem[e] | mem[e + 1] << 8
            length = mem[e + 2] | mem[e + 3] << 8
            delay, bank = mem[e + 4], mem[e + 5]
            samples = [mem.banks[bank][start - 0xC000 + i] for i in range(length)]
            total_bytes += length

            log = []
            spec = Spectrum(snap, portlog=log, cmio=True)
            spec.mem[0x5673] = 1   # speech on (the menu's Sound option)
            stub = [0xF3, 0x31, 0xF0, 0x7F, 0x3E, n, 0xCD, PLAYER & 0xFF, PLAYER >> 8, 0x18, 0xFE]
            for i, b in enumerate(stub):
                spec.mem[STUB + i] = b
            spec.sim.registers[PC] = STUB
            t0 = spec.sim.registers[T]
            spec.run_tstates(400 * spec.frame, stop=STUB + len(stub) - 2)
            took = spec.sim.registers[T] - t0
            vol8 = [t for t, kind, *rest in log if kind == "AY" and rest[0] == 8]
            # The phrase's samples are the last `length` writes of register 8
            # (the bleeps before it write register 8 too).
            play = vol8[-length:]
            per_sample = (play[-1] - play[0]) / (len(play) - 1)
            rate = CLOCK128 / per_sample

            pcm = []
            for s in samples:
                i = ((s - 256 if s & 0x80 else s) >> 1) + 0x40 & 0xFF
                level = sum(AY_LEVELS[vol[c][i] & 15] for c in range(3)) / 3
                pcm.append(int((level * 2 - 1) * 30000))
            wav = out / f"zx_speech_{n}.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(round(rate))
                w.writeframes(b"".join(struct.pack("<h", v) for v in pcm))
            print(f"phrase {n}: bank {bank} &{start:04X}-&{start + length - 1:04X}, {length} samples, "
                  f"delay {delay}; {per_sample:.1f} T a sample = {rate:.0f} Hz, {length / rate:.2f} s; "
                  f"the call took {took} T ({took / spec.frame:.1f} frames) -> {wav}")
    finally:
        Path(snap).unlink()
    print(f"speech: {total_bytes} bytes of samples")


if __name__ == "__main__":
    sys.exit(main())
