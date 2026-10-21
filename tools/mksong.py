#!/usr/bin/env python3
"""The title song's two candidates (decision 5), as the SN76489 would play
them, for tools/songwav.mjs to render: the ST's sampled song through one
channel's sixteen levels, and David Lowe's AY tune from the Spectrum 128K
converted to the SN's registers (docs/research/song.md).

    mksong.py PRG CAPTURE.JSON OUTDIR

CAPTURE.JSON is tools/zx_song.py's capture. Each output is a chip's writes
in time, which songwav.mjs renders: {"chip", "hz" (the writes' clock),
"end", "writes": [[time, byte]] for the SN or [[time, register, value]]
for the AY}. OUTDIR gets:

- st_4096.json, st_6144.json: the ST's song resampled from its 9,830.4 Hz
  (Timer A's data 5) to each rate, exact ratios of 5:12 and 5:8, and each
  sample made the nearest of the chip's levels as tools/mkspeech.py makes
  the speech's (scaled to the whole range, the error carried to the next),
  written to tone channel 1 at period 1 as the speech player writes them,
  a sample a tick.
- zx_bass.json, zx_octave.json: the tune's AY registers after each tick,
  turned into the SN's, the ticks evenly spaced at the capture's mean rate,
  as a VIA timer would space them; a tone below the SN's lowest played by
  a timer switching the channel's volume each half-cycle (zx_bass), or
  taken up octaves until it fits (zx_octave).
- zx_ay.json: the AY's writes as the Spectrum made them, for a reference
  render of the original.
- costs.json: what each costs, which it also prints.

The conversion, tick by tick, for each AY channel to the SN's tone channel
of the same number:

- The period: the AY's tone is 1,773,450 / (16 x P) Hz, the SN's
  4,000,000 / (32 x N), so N = 125,000 / 110,840.6 x P, rounded. Past
  N's 10 bits (below 122 Hz) the tone is bass (above).
- The volume: the channel's level, or with register 8-10's bit 4 the
  envelope's at the tick (its shape and period from registers 11-13, from
  the tick that last wrote 13), through VOLUME, ym2sn.py's table, which nm
  took by ear (its decision 16): each AY step a 2 dB step of the SN's.
  A channel whose tone the mixer (register 7) turns off is silent on its
  tone channel.
- The noise: the SN's white noise, as loud as the loudest channel the mixer
  gives it to, at the SN's faster rate (7,812.5 shifts a second) for an
  AY noise period up to NOISE_SLOW and the slower (3,906.25) above; its
  control written only when its rate changes while it's heard, since a
  write restarts the SN's shift register (nm's decision 17).
"""
import argparse
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mkspeech  # noqa: E402
import st_prg  # noqa: E402
import st_samples  # noqa: E402

BBC_HZ = 2000000                 # the writes' clock: the 6502's cycles
SN_HZ = 4000000 / 32             # a tone of period N is SN_HZ / N
SN_PERIODS = 1024
VIA_HZ = 1000000                 # a bass edge is timed in the VIA's microseconds
BASS_US = 4                      # a bass half-cycle's microseconds a unit of the SN's period
BASS_FLAG = 0x40                 # a stream's bass period: bit 7 clear (no latch), bit 6 set
SPEECH_CHANNEL = 1               # the speech player's tone channel
VOLUME = [15 if v == 0 else 0 if v == 15 else 15 - (v + (v & 1)) for v in range(16)]
NOISE_SLOW = 18                  # an AY noise period above this takes the SN's slower rate
NOISE_WHITE = 4
SILENT = 15
SAMPLE_RATES = (4096, 6144)
TICK_CYCLES = 150                # the speech player's tick (decision 38)
SECTOR = 256
TRACK_SECTORS = 10
IRQ_CYCLES = 50                  # an interrupt's own cost (docs/research/beeb.md, section 5)
WRITE_CYCLES = 36                # a chip write a sample, past the interrupt's (the same)
FIELD_HZ = 50
SNR_BAND = 1000                  # Hz


# ---------------------------------------------------------------------------
# The ST's sampled song

def resample(x, up, down):
    """By up:down: zeros between the samples, low-passed below the lower
    Nyquist by a windowed sinc (as mkspeech.resample, at any ratio), every
    down-th kept."""
    u = np.zeros(len(x) * up)
    u[::up] = x * up
    k = 32 * max(up, down)
    taps = np.arange(-k, k + 1)
    fc = 0.95 / (2 * max(up, down))
    h = 2 * fc * np.sinc(2 * fc * taps) * np.blackman(len(taps))
    n = len(u) + len(h) - 1
    size = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(u, size) * np.fft.rfft(h, size), size)[k:k + len(u)]
    return y[::down]


def st_song(prg):
    name, addr, played, ctrl, data, _ = next(s for s in st_samples.SAMPLES if s[0] == "star")
    count, _ = struct.unpack_from(">IH", prg.image, addr)
    pcm = np.array([b - 256 if b >= 128 else b for b in prg.image[addr + 6:addr + 6 + count]], float)
    st_hz = st_samples.MFP_HZ / st_samples.PRESCALE[ctrl] / data
    return pcm, st_hz, played


def sample_writes(levels, rate):
    writes = [[0, 0x80 | SPEECH_CHANNEL << 5 | 1], [0, 0]]       # period 1
    last = None
    for i, k in enumerate(levels):
        if k != last:
            writes.append([round(i * BBC_HZ / rate), 0x90 | SPEECH_CHANNEL << 5 | k])
            last = k
    end = round(len(levels) * BBC_HZ / rate)
    writes.append([end, 0x90 | SPEECH_CHANNEL << 5 | SILENT])
    return {"chip": "sn", "hz": BBC_HZ, "end": end, "writes": writes}


def snr(x, levels, rate):
    """The levels' error against the resampled song, scaled as quantise
    scales it: in all, and below SNR_BAND, where the carried error leaves
    less of it."""
    want = (x - x.min()) / (x.max() - x.min())
    err = want - np.array([mkspeech.LEVELS[k] for k in levels])
    f = np.fft.rfftfreq(len(want), 1 / rate)
    band = f < SNR_BAND
    s, e = np.abs(np.fft.rfft(want - want.mean())) ** 2, np.abs(np.fft.rfft(err - err.mean())) ** 2
    return {"snr_db": 10 * math.log10(s.sum() / e.sum()),
            "snr_band_db": 10 * math.log10(s[band].sum() / e[band].sum())}


def sample_costs(n, rate):
    packed = (n + 1) // 2 + 1                                  # two a byte, and the end
    sectors = -(-packed // SECTOR)
    return {"rate": rate, "samples": n, "seconds": n / rate, "bytes": packed, "sectors": sectors,
            "tracks": sectors / TRACK_SECTORS, "read_bytes_s": rate / 2,
            "track_every_s": TRACK_SECTORS * SECTOR / (rate / 2),
            "cpu": TICK_CYCLES * rate / BBC_HZ, "cycles_field": TICK_CYCLES * rate / FIELD_HZ}


# ---------------------------------------------------------------------------
# The AY tune

def envelope(shape, n):
    """The AY's envelope level n steps after register 13's write, 16 steps a
    cycle (bits: 8 continue, 4 attack, 2 alternate, 1 hold)."""
    if not shape & 8:
        shape = 9 if not shape & 4 else 15
    attack = bool(shape & 4)
    cycle, step = divmod(n, 16)
    if shape & 1 and cycle:
        return 15 if attack ^ bool(shape & 2) else 0
    up = attack ^ (bool(shape & 2) and cycle & 1)
    return step if up else 15 - step


class SN:
    """The chip's registers as written, and the writes, timed."""

    def __init__(self):
        self.period = [None] * 3
        self.att = [None] * 4
        self.noise = None
        self.writes = []

    def tone(self, t, c, n):
        if self.period[c] != n:
            self.writes += [[t, 0x80 | c << 5 | n & 15], [t, n >> 4]]
            self.period[c] = n

    def volume(self, t, c, a):
        if self.att[c] != a:
            self.writes.append([t, 0x90 | c << 5 | a])
            self.att[c] = a

    def noise_control(self, t, v):
        if self.noise != v:
            self.writes.append([t, 0xE0 | v])
            self.noise = v


def convert(cap, bass, ticks=None, records=None):
    """The tune's SN writes in time; and per tick, what a stream of it would
    carry: the SN's writes at the tick, but for a bass channel its period
    past 10 bits (two bytes, flagged by BASS_FLAG, which no SN write has)
    and its level (one) where they change, as its edges are the player's
    own: a half-cycle is BASS_US microseconds a unit of the SN's period, as
    nm's bass.6502 times them.

    bass is True or False for every channel, or one of each by channel (a
    channel without it takes its low notes up octaves). ticks plays on past
    the pass, its writes again, as the Spectrum loops it. records, a list,
    gets each tick's state once it's done, for tools/songcheck.mjs (via
    tools/songmodel.py): the AY's registers 0-13, whether register 13 was
    written (the envelope restarted), the SN's periods and attenuations as
    last written (a bass channel's attenuation is its edges'), the noise's
    control and how often the tick wrote it, and each bass channel's
    half-cycle in microseconds (0: none) and attenuation."""
    ay_hz = cap["ay_hz"]
    length = cap["length"]
    tick_s = (cap["ticks"][length] - cap["ticks"][0]) / cap["cpu_hz"] / length
    ratio = SN_HZ * 16 / ay_hz
    timer = bass if isinstance(bass, (list, tuple)) else (bass,) * 3
    sn = SN()
    reg = [0] * 16
    env_at = 0                                  # the tick register 13 was last written
    stream = []
    bass_made = set()                           # the SN writes a bass channel makes, by index
    edges = 0
    edge = [None] * 3                          # bass: the next edge's time (s), or None
    on = [False] * 3                            # bass: the half-cycle sounding
    held = [None] * 3                           # bass: the attenuation it sounds at
    half = [None] * 3                           # bass: the half-cycle (s)
    for c in range(4):
        sn.volume(0, c, SILENT)
    for k in range(ticks or length):
        t0 = k * tick_s
        while True:
            due = [(edge[c], c) for c in range(3) if edge[c] is not None and edge[c] < t0]
            if not due:
                break
            te, c = min(due)
            on[c] = not on[c]
            sn.volume(round(te * BBC_HZ), c, held[c] if on[c] else SILENT)
            edge[c] = te + half[c]
            edges += 1
        restarted = False
        for _, r, v in cap["writes"][k % length]:
            reg[r] = v
            if r == 13:
                env_at = k
                restarted = True
        t = round(t0 * BBC_HZ)
        before = len(sn.writes)
        items = []
        steps = math.floor((k - env_at) * tick_s * ay_hz / (16 * max(1, reg[11] | reg[12] << 8)))
        env = envelope(reg[13], steps)
        mixer = reg[7]
        noise_level = 0
        for c in range(3):
            level = env if reg[8 + c] & 16 else reg[8 + c] & 15
            tone_on = not mixer >> c & 1
            if not mixer >> (3 + c) & 1:
                noise_level = max(noise_level, level)
            p = max(1, reg[2 * c] | (reg[2 * c + 1] & 15) << 8)
            n = round(p * ratio)
            att = VOLUME[level] if tone_on else SILENT
            if n < SN_PERIODS:
                edge[c] = half[c] = held[c] = None
                sn.tone(t, c, n)
                sn.volume(t, c, att)
            elif timer[c]:
                h = BASS_US * n / VIA_HZ
                mark = len(sn.writes)
                if edge[c] is None:
                    sn.tone(t, c, 1)
                    on[c] = True
                    edge[c] = t0 + h
                if h != half[c]:
                    items += [BASS_FLAG | c << 4 | n >> 8, n & 255]
                if att != held[c]:
                    items.append(0x90 | c << 5 | att)
                half[c], held[c] = h, att
                sn.volume(t, c, att if on[c] else SILENT)
                bass_made.update(range(mark, len(sn.writes)))
            else:
                while n >= SN_PERIODS:
                    p /= 2
                    n = round(p * ratio)
                sn.tone(t, c, n)
                sn.volume(t, c, att)
        if noise_level:
            sn.noise_control(t, NOISE_WHITE | (0 if reg[6] <= NOISE_SLOW else 1))
        sn.volume(t, 3, VOLUME[noise_level])
        stream.append(items + [w[1] for i, w in enumerate(sn.writes[before:], before) if i not in bass_made])
        if records is not None:
            records.append({
                "ay": reg[:14], "env": restarted, "tone": sn.period[:], "att": sn.att[:], "noise": sn.noise,
                "noise_w": sum(1 for w in sn.writes[before:] if w[1] & 0xF0 == 0xE0),
                "half": [round(h * VIA_HZ) if h else 0 for h in half], "held": held[:],
            })
    end = round((ticks or length) * tick_s * BBC_HZ)
    for c in range(4):
        sn.volume(end, c, SILENT)
    sn.writes.sort(key=lambda w: w[0])
    return {"chip": "sn", "hz": BBC_HZ, "end": end, "writes": sn.writes}, stream, edges, tick_s


def stream_bytes(stream):
    """A simple stream: per tick with something to write a byte (its count
    of bytes, and how many ticks with nothing follow, a nibble each, with
    another such byte for each 15 more), then its bytes."""
    out = bytearray()
    k = 0
    while k < len(stream):
        assert len(stream[k]) < 16
        wait = 0
        while k + 1 + wait < len(stream) and not stream[k + 1 + wait]:
            wait += 1
        out.append(len(stream[k]) | min(wait, 15) << 4)
        out += bytes(stream[k])
        for more in range(1, wait // 15 + 1):
            out.append(min(wait - 15 * more, 15) << 4)
        k += 1 + wait
    return bytes(out)


def zx_costs(stream, edges, tick_s):
    ticks = len(stream)
    seconds = ticks * tick_s
    fields = seconds * FIELD_HZ
    sizes = [len(w) for w in stream]
    raw = stream_bytes(stream)
    return {
        "ticks": ticks, "tick_hz": 1 / tick_s, "seconds": seconds,
        "items": sum(sizes), "items_tick": sum(sizes) / ticks, "items_tick_max": max(sizes),
        "ticks_writing": sum(1 for n in sizes if n),
        "stream_bytes": len(raw), "stream_deflated": len(zlib.compress(raw, 9)),
        "bass_edges": edges, "bass_edges_s": edges / seconds,
        # an interrupt a tick and a write a byte; a bass edge an interrupt and a write
        "stream_cycles_field": (ticks * IRQ_CYCLES + sum(sizes) * WRITE_CYCLES
                                + edges * (IRQ_CYCLES + WRITE_CYCLES)) / fields,
    }


def usage(cap):
    """What the tune asks of the AY, from its registers after each tick:
    by channel, the ticks it sounds a tone (the mixer's tone on, a level
    above 0), those below the SN's lowest, those with the noise, its tone
    periods, and whether it uses the envelope; the noise's periods, and the
    envelope's shapes and periods as register 13's writes start them."""
    reg = [0] * 16
    ratio = SN_HZ * 16 / cap["ay_hz"]
    chans = [{"tone": 0, "low": 0, "noise": 0, "envelope": 0, "periods": set(), "cents_max": 0.0, "cents_sq": 0.0}
             for _ in range(3)]
    noise_periods, starts = {}, {}
    both_low = 0
    for ws in cap["writes"][:cap["length"]]:
        for _, r, v in ws:
            reg[r] = v
            if r == 13:
                key = f"{v}:{reg[11] | reg[12] << 8}"
                starts[key] = starts.get(key, 0) + 1
        lows = 0
        for c, ch in enumerate(chans):
            level = reg[8 + c]
            if not level:
                continue
            ch["envelope"] += bool(level & 16)
            p = reg[2 * c] | (reg[2 * c + 1] & 15) << 8
            if not reg[7] >> c & 1:
                ch["tone"] += 1
                ch["periods"].add(p)
                n = round(max(1, p) * ratio)
                if n >= SN_PERIODS:
                    ch["low"] += 1
                    lows += 1
                else:
                    cents = abs(1200 * math.log2(max(1, p) * ratio / n))
                    ch["cents_max"] = max(ch["cents_max"], cents)
                    ch["cents_sq"] += cents * cents
            if not reg[7] >> (3 + c) & 1:
                ch["noise"] += 1
                noise_periods[reg[6]] = noise_periods.get(reg[6], 0) + 1
        both_low += lows > 1
    for ch in chans:
        ps = sorted(ch.pop("periods"))
        ch["period_min"], ch["period_max"] = ps[0], ps[-1]
        ch["cents_rms"] = math.sqrt(ch.pop("cents_sq") / max(1, ch["tone"] - ch["low"]))
    return {"channels": chans, "two_low": both_low, "noise_periods": dict(sorted(noise_periods.items())),
            "envelopes": dict(sorted(starts.items(), key=lambda kv: int(kv[0].split(":")[1])))}


def ay_reference(cap):
    t0 = cap["ticks"][0]
    writes = [[t - t0, r, v] for ws in cap["writes"] for t, r, v in ws]
    return {"chip": "ay", "hz": cap["cpu_hz"], "ay_hz": cap["ay_hz"],
            "end": cap["ticks"][cap["length"]] - t0, "writes": writes}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("zx")
    ap.add_argument("outdir")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    costs = {}

    prg = st_prg.load(args.prg)
    pcm, st_hz, played = st_song(prg)
    for rate in SAMPLE_RATES:
        g = math.gcd(round(st_hz * 5), rate * 5)
        up, down = rate * 5 // g, round(st_hz * 5) // g
        assert abs(st_hz * up / down - rate) < 1e-9
        x = resample(pcm, up, down)
        levels = mkspeech.quantise(x)
        (out / f"st_{rate}.json").write_text(json.dumps(sample_writes(levels, rate)) + "\n")
        costs[f"st_{rate}"] = sample_costs(len(levels), rate) | {"ratio": f"{up}:{down}"} | snr(x, levels, rate)
    costs["st_original"] = {"rate": st_hz, "samples": len(pcm), "played": played,
                            "seconds": played / st_hz, "bytes": played}

    cap = json.loads(Path(args.zx).read_text())
    for name, bass in (("zx_bass", True), ("zx_octave", False)):
        writes, stream, edges, tick_s = convert(cap, bass)
        (out / f"{name}.json").write_text(json.dumps(writes) + "\n")
        costs[name] = zx_costs(stream, edges, tick_s)
    (out / "zx_ay.json").write_text(json.dumps(ay_reference(cap)) + "\n")
    costs["zx_player"] = {"code": cap["code"][1] - cap["code"][0], "data": len(cap["data"]),
                          "ay_writes": sum(len(w) for w in cap["writes"]),
                          "work_mean": cap["work_mean"], "work_max": cap["work_max"]}
    costs["zx_usage"] = usage(cap)
    (out / "costs.json").write_text(json.dumps(costs, indent=1) + "\n")

    for rate in SAMPLE_RATES:
        c = costs[f"st_{rate}"]
        print(f"st_{rate}: {c['samples']} samples, {c['seconds']:.2f} s, {c['bytes']} bytes, "
              f"{c['sectors']} sectors ({c['tracks']:.1f} tracks); read {c['read_bytes_s']:.0f} bytes/s, "
              f"a track every {c['track_every_s']:.2f} s; {c['cpu']:.1%} of the CPU, "
              f"{c['cycles_field']:.0f} cycles a field; signal to error {c['snr_db']:.1f} dB, "
              f"{c['snr_band_db']:.1f} dB below {SNR_BAND} Hz")
    for name in ("zx_bass", "zx_octave"):
        c = costs[name]
        print(f"{name}: {c['ticks']} ticks at {c['tick_hz']:.2f} Hz, {c['seconds']:.2f} s; {c['items']} bytes "
              f"to write ({c['items_tick']:.2f} a tick, at most {c['items_tick_max']}); stream {c['stream_bytes']} "
              f"bytes ({c['stream_deflated']} deflated); bass edges {c['bass_edges']} "
              f"({c['bass_edges_s']:.1f} a second); a stream player about {c['stream_cycles_field']:.0f} "
              f"cycles a field")
    p = costs["zx_player"]
    print(f"zx_player: the Z80 player {p['code']} bytes, its data {p['data']} bytes; its tick "
          f"{p['work_mean']:.0f} T on average, {p['work_max']} at most")
    u = costs["zx_usage"]
    for c, ch in enumerate(u["channels"]):
        print(f"zx channel {'ABC'[c]}: a tone {ch['tone']} ticks ({ch['low']} below the SN's lowest), "
              f"periods {ch['period_min']}-{ch['period_max']}, the SN's off by {ch['cents_rms']:.1f} cents "
              f"(RMS), {ch['cents_max']:.1f} at most; noise {ch['noise']} ticks; "
              f"the envelope {ch['envelope']} ticks")
    print(f"zx: two channels below the SN's lowest at once {u['two_low']} ticks; noise periods (ticks) "
          f"{u['noise_periods']}; envelopes started (shape:period) {u['envelopes']}")


if __name__ == "__main__":
    main()
