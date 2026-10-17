#!/usr/bin/env python3
"""List, and optionally export as WAV, the sampled sounds embedded in
Starglider's AUTO/STAR.PRG (Atari ST): Clare Edgeley's four speech clips
(clare1-4.snd) and the title song (star.snd).

    st_samples.py PRG               print the table
    st_samples.py PRG --wav DIR     also write DIR/<name>.wav (8-bit, at the
                                    rate the ST plays them back)

Each block is the .snd file as it was on Argonaut's disc: a 6-byte header
(a long, the sample count; a word, the recording rate in Hz) then signed
8-bit samples. At start-up the game flips them to unsigned (EOR &80), and
the Timer A interrupt at &1AF8 plays one byte a tick through a 3 x 256
YM2149 volume table (&1B4A). Each start (sample_start, &1A50) gives the
address, the byte count and the MFP Timer A control/data pair; control 4
divides the MFP's 2.4576MHz clock by 50, so the rate is 49152 / data Hz.
"""
import argparse
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

MFP_HZ = 2457600
PRESCALE = {1: 4, 2: 10, 3: 16, 4: 50, 5: 64, 6: 100, 7: 200}
# (name, address, bytes played, Timer A control, data, where it is started)
SAMPLES = [
    ("clare1", 0x18DB4, 0x1B80, 4, 8, "&29A2: L, launch a missile"),
    ("clare2", 0x1A934, 0x1D00, 4, 8, "&56BA: docked, rearmed, the launch countdown starts"),
    ("clare3", 0x1C634, 0x1680, 4, 8, "&1F5A: shields (&260) below &2EE0, every 128 frames"),
    ("clare4", 0x1DCB4, 0x1B00, 4, 8, "&1F9C: energy (&25E) below &2EE0, every 128 frames"),
    ("star", 0x1F7B4, 0x2BC00, 4, 5, "&2290: the title song, looped"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("--wav")
    args = ap.parse_args()
    prg = st_prg.load(args.prg)
    print("| Sample | Block | Header count | Recorded at | Bytes played | Plays at | Seconds | Started |")
    print("|---|---|---|---|---|---|---|---|")
    for name, addr, played, ctrl, data, where in SAMPLES:
        count, rate = struct.unpack_from(">IH", prg.image, addr)
        hz = MFP_HZ / PRESCALE[ctrl] / data
        print(f"| {name} | &{addr:05X}-&{addr + 6 + count:05X} | {count} | {rate} Hz | {played} | "
              f"{hz:.1f} Hz | {played / hz:.2f} | {where} |")
        if args.wav:
            out = Path(args.wav)
            out.mkdir(parents=True, exist_ok=True)
            pcm = bytes((b ^ 0x80) for b in prg.image[addr + 6:addr + 6 + count])
            with wave.open(str(out / f"{name}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(1)
                w.setframerate(round(hz))
                w.writeframes(pcm)


if __name__ == "__main__":
    main()
