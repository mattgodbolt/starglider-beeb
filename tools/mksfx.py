#!/usr/bin/env python3
"""The sound effects' tables (the ST's), as Baron source, for the port's
SN76489 (decision 5; docs/research/st.md, "Music and effects").

    mksfx.py PRG OUT JSON       write OUT (build/gen/sfx.6502) and JSON
                                (build/gen/sfx.json, for tools/sfxcheck.mjs)

PRG is the ST's AUTO/STAR.PRG. The build runs this: nothing derived from
the original is committed. sfx_start (&00110) takes each effect from the
table at &01854 (24 entries: a routine and its parameter block). The
eight the game starts (STARTED) are ported, each read from its block and
its routine's code, whose instructions are asserted here:

- the noise (&004A8: effects 0-3): the noise period, the envelope's
  period and shape, all three channels noise at the envelope's level, and
  the lock (&29C) that keeps any other effect out for 22 VBLs. The SN's
  noise runs off tone 2, whose period is the YM's noise period: both
  shift at 125 kHz over it (Hatari's sound.c; jsbeeb's soundchip.js). The
  envelope's level, by the field, takes the SN's nearest attenuation to
  the three channels' sum (or two, once a sweep's end has turned channel
  A's volume to 0), from Paulo Simoes' measurements of an ST's YM2149
  (MEASURED).
- the sweeps (&0052E by 1, &00626 by 4): tone A's period from a start to
  an end at Timer A's rate, as many times as d1 says. The SN's tone
  period is the YM's: both are 125 kHz over it.
- the two tones (&00180): tone A between two periods every 32 of Timer
  A's ticks, d1 counting the halves.

Timer A's rate is 2.4576 MHz over its prescaler and data; the port's
timer (System VIA T1, at 1 MHz, free-running every latch + 2 cycles)
ticks at it up to MAX_TICK_HZ, and a sweep faster than that (8 and 9,
whose sweeps last 33 ms) takes k of the ST's ticks a tick, its step k
times the ST's: the vertical sync's handler, with a key held, keeps
interrupts off for longer than the ST's fastest ticks, and the VIA's flag
takes two ticks for one (tools/sfxcheck.mjs holds a key through them).
A sweep then ends at the first period at or past its end.

The tone's attenuation is the one channel's level against the three
channels' at full, the loudest the effects (and the speech) reach, which
is the SN's full: the ST's balance between them kept.

Each effect's start is a record (sfx.6502's sfx_record): the sound's
state it sets, from ta_kind (Timer A's effects) or sfx_mix (the noise,
which leaves a Timer A effect ticking), to noise_att, in sound.6502's
order (STATE); the chip's bytes; and a Timer A effect's latch. Two more
records silence it: sample_start's, as the ST's mixer goes all off for a
sample, and sound_init's, every channel.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

TABLE, EFFECTS = 0x01854, 24
# sfx_start's callers: 0 an enemy's laser hit (&07ED0), 1 a mine and ramming
# (&07B8A, &020C4), 2 the laser's hit and the missile's end (&087EE, &07A4C),
# 3 scraping the ground and the launch countdown (&0209A, &0566A), 8 the
# cheat's prompt and refuelling (&02898, &0858E), 9 the cheat's end
# (&028AA), 16 docking (&085D2), 20 the laser and the beeps (&086BE,
# &04B14).
STARTED = {0, 1, 2, 3, 8, 9, 16, 20}
NOISE, SWEEP1, SWEEP4, TWO = 0x004A8, 0x0052E, 0x00626, 0x00180
MFP_HZ = 2457600
PRESCALE = [None, 4, 10, 16, 50, 64, 100, 200]      # by Timer A's control, 1-7
VIA_HZ = 1000000
MAX_TICK_HZ = 1200
YM_CLOCK = 250000                                    # the YM's counters, 2 MHz / 8
FIELD = 312 * 64 / 1e6                               # screen_mode's field: 312 lines, not interlaced
LOCK_VBLS = 22
SN_PERIOD_MAX = 1023
SN_FLOOR_DB = 28                                     # attenuation 14; 15 is off
SN_TONE0, SN_TONE1, SN_TONE2, SN_NOISE, SN_VOL, SN_OFF = 0x80, 0xA0, 0xC0, 0xE0, 0x10, 15
SN_WHITE_TONE2 = SN_NOISE | 4 | 3
# The ST's output, by channel volume, with one, two and three channels at it
# (volume_table[v][0][0], [v][v][0] and [v][v][v]): Paulo Simoes'
# measurements of an ST's YM2149, as Hatari keeps them
# (src/includes/ym2149_fixed_vol.h).
MEASURED = {
    1: [0, 120, 251, 385, 598, 840, 1258, 1725, 2536, 3483, 5151, 7054, 10367, 14634, 22931, 34469],
    2: [0, 283, 553, 828, 1261, 1747, 2572, 3487, 5048, 6847, 9780, 13292, 19431, 26871, 40524, 55377],
    3: [0, 453, 863, 1276, 1916, 2640, 3854, 5177, 7432, 9829, 14111, 18672, 26557, 35434, 49971, 65119],
}
# sound.6502's state, in its order: Timer A's effect, then the mixer's and
# the noise's
STATE = ["ta_kind", "ta_lo", "ta_hi", "ta_start_lo", "ta_start_hi", "ta_end_lo", "ta_end_hi",
         "ta_step", "ta_tick", "ta_written", "sfx_mix", "noise_from", "sfx_lock",
         "env_pos", "env_pos+1", "env_rate", "env_rate+1", "noise_att"]
KIND_SWEEP, KIND_TWO = 0x01, 0x80                    # ta_kind's (bit 7: the two tones)
MIX_TONE, MIX_NOISE = 0x01, 0x40                     # sfx_mix's


def code(prg, at, words, what):
    got = [prg.u16(at + 2 * i) for i in range(len(words))]
    assert got == words, f"&{at:05X} ({what}): {' '.join(f'{w:04X}' for w in got)}"


def check_code(prg):
    """The routines' instructions the records stand for."""
    code(prg, 0x004BE, [0x13FC, 0x0047, 0xFFFF, 0x8802], "the noise's mixer &47")
    for at in (0x004CE, 0x004DE, 0x004EE):
        code(prg, at, [0x13FC, 0x0010, 0xFFFF, 0x8802], "a channel at the envelope's level")
    code(prg, 0x00520, [0x33FC, LOCK_VBLS, 0x0000, 0x029C], "the lock")
    for at in (0x0058E, 0x00686, 0x0020A):
        code(prg, at, [0x13FC, 0x007E, 0xFFFF, 0x8802], "tone A's mixer &7E")
    for at in (0x0059E, 0x00696, 0x0021A):
        code(prg, at, [0x13FC, 0x000F, 0xFFFF, 0x8802], "tone A at 15")
    code(prg, 0x005AE, [0x5279, 0x0000, 0x1A00], "the sweep by 1")
    code(prg, 0x006A6, [0x5879, 0x0000, 0x1A00], "the sweep by 4")
    code(prg, 0x00238, [0xB03C, 0x0020], "the second tone's tick")
    code(prg, 0x0023E, [0xB03C, 0x0040], "the first tone's")
    for at in (0x00618, 0x00710, 0x002BA):
        code(prg, at, [0x13FC, 0x0000, 0xFFFF, 0x8802], "tone A's volume 0 at the end")


def rate(tacr, tadr):
    return MFP_HZ / (PRESCALE[tacr] * (tadr or 256))


def level5(levels):
    """The YM's 32 envelope levels from its 16 volumes' (the volume v is
    the level 2v + 1), the levels between geometric, as Hatari makes them
    (interpolate_volumetable)."""
    v = [0.0] * 32
    for vol in range(16):
        v[2 * vol + 1] = levels[vol]
    v[0], v[1] = v[1], v[3]
    v[3] = math.sqrt(v[1] * v[5])
    for lv in range(2, 31, 2):
        v[lv] = math.sqrt(v[lv - 1] * v[lv + 1])
    return v


def attenuation(amp, ref):
    """The SN's nearest attenuation (2 dB a step) to amp against ref, 15
    (off) past its floor."""
    if amp <= 0:
        return 15
    db = -20 * math.log10(amp / ref)
    return 15 if db > SN_FLOOR_DB + 1 else min(14, max(0, round(db / 2)))


def effect(prg, n):
    routine, block = prg.u32(TABLE + 8 * n), prg.u32(TABLE + 8 * n + 4)
    e = {"effect": n, "routine": routine, "block": block}
    if routine == NOISE:
        noise, ep_lo, ep_hi, shape = (prg.u8(block + i) for i in range(4))
        ep = ep_hi << 8 | ep_lo
        assert shape in (0, 1, 2, 3, 9), f"effect {n}: envelope shape {shape} isn't a fall that holds at 0"
        assert ep, f"effect {n}: envelope period 0"
        e.update(kind="noise", noise=noise, env_period=ep, shape=shape,
                 clock=max(noise & 31, 1),                      # (the YM takes 0 as 1)
                 env_rate=round(256 * YM_CLOCK * FIELD / ep))   # envelope steps a field, 8.8
    elif routine in (SWEEP1, SWEEP4):
        start, end, tacr, tadr = (prg.u16(block + 2 * i) for i in range(4))
        step = 1 if routine == SWEEP1 else 4
        e.update(kind="sweep", start=start, end=end, step=step, tacr=tacr & 0xFF, tadr=tadr & 0xFF)
    elif routine == TWO:
        tacr, tadr, f1, c1, f2, c2 = (prg.u8(block + i) for i in range(6))
        e.update(kind="two", tacr=tacr, tadr=tadr, first=c1 << 8 | f1, second=c2 << 8 | f2)
    else:
        e["kind"] = "other"
    if e["kind"] in ("sweep", "two"):
        hz = rate(e["tacr"], e["tadr"])
        k = math.ceil(hz / MAX_TICK_HZ) if e["kind"] == "sweep" else 1
        assert e["kind"] == "sweep" or hz <= MAX_TICK_HZ, f"effect {e['effect']}: two tones at {hz} Hz"
        e.update(rate=hz, k=k, latch=round(VIA_HZ * k / hz) - 2)
    return e


def split(p):
    """A period as the tick keeps it: its low 4 bits (the SN's latch byte's)
    and the rest (its data byte's)."""
    assert 0 < p <= SN_PERIOD_MAX, f"period {p} isn't the SN's"
    return p & 15, p >> 4


def record(e, att3, tone_att):
    """An effect's start: (the state's first variable, its values, the
    chip's bytes, the latch or None)."""
    if e["kind"] == "noise":
        lo, hi = split(e["clock"])
        state = [MIX_NOISE, 0, LOCK_VBLS, 0, 0, e["env_rate"] & 0xFF, e["env_rate"] >> 8, att3[31]]
        chip = [SN_TONE0 | SN_VOL | SN_OFF, SN_TONE2 | SN_VOL | SN_OFF, SN_TONE2 | lo, hi,
                SN_WHITE_TONE2, SN_NOISE | SN_VOL | att3[31]]
        return "sfx_mix", state, chip, None
    if e["kind"] == "sweep":
        assert (e["end"] - e["start"]) % e["step"] == 0 and e["end"] > e["start"], f"effect {e['effect']} never ends"
        split(e["end"] - e["step"])                     # (the last period written)
        first, (s_lo, s_hi), (e_lo, e_hi) = [], split(e["start"]), (e["end"] & 15, e["end"] >> 4)
        kind, written, step = KIND_SWEEP, 0xFF, e["step"] * e["k"]
        assert step < 16, f"effect {e['effect']}: a step of {step} carries more than once"
    else:
        (s_lo, s_hi), (e_lo, e_hi) = split(e["first"]), split(e["second"])
        first = [SN_TONE0 | s_lo, s_hi]                 # the first tone at once, as &00180 writes it
        kind, written, step = KIND_TWO, s_hi, 0
    state = [kind, s_lo, s_hi, s_lo, s_hi, e_lo, e_hi, step, 0, written, MIX_TONE, 0, 0, 0, 0, 0, 0, SN_OFF]
    chip = first + [SN_NOISE | SN_VOL | SN_OFF, SN_TONE0 | SN_VOL | tone_att]
    assert 0 < e["latch"] < 0x10000
    return "ta_kind", state, chip, e["latch"]


def quiet(chip):
    return "ta_kind", [0] * 9 + [0xFF] + [0] * 7 + [SN_OFF], chip, 0


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    prg = st_prg.load(sys.argv[1])
    check_code(prg)
    effects = [effect(prg, n) for n in range(EFFECTS)]
    ref = MEASURED[3][15]
    att3 = [attenuation(a, ref) for a in level5(MEASURED[3])]
    att2 = [attenuation(a, ref) for a in level5(MEASURED[2])]
    tone_att = attenuation(MEASURED[1][15], ref)

    records, at = [], [0xFF] * EFFECTS
    named = {}
    for name, rec in [(n, record(effects[n], att3, tone_att)) for n in sorted(STARTED)] + [
            ("SFX_QUIET", quiet([SN_TONE0 | SN_VOL | SN_OFF, SN_NOISE | SN_VOL | SN_OFF])),
            ("SFX_INIT", quiet([c | SN_VOL | SN_OFF for c in (SN_TONE0, SN_TONE1, SN_TONE2, SN_NOISE)]))]:
        first, state, chip, latch = rec
        assert len(state) == len(STATE) - STATE.index(first) and chip
        offset = sum(len(r) for r in records)
        if isinstance(name, int):
            at[name] = offset
            effects[name]["ported"] = True
        else:
            named[name] = offset
        records.append([f"{first} - ta_kind"] + state + [len(chip)] + chip +
                       ([latch & 0xFF, latch >> 8] if latch else []))
    assert sum(len(r) for r in records) < 0xFF          # (sfx_record's Y; &FF is none)

    out = ["; Generated by tools/mksfx.py from the ST's STAR.PRG: do not edit.", ""]
    out += [f"ASSERT {v} - ta_kind = {i}" for i, v in enumerate(STATE)]
    out += [f"ASSERT SFX_STATE = {len(STATE)}", f"ASSERT SFX_KIND_TWO = &{KIND_TWO:02X}",
            f"ASSERT SFX_MIX_TONE = &{MIX_TONE:02X} AND SFX_MIX_NOISE = &{MIX_NOISE:02X}"]
    out += [f"{k} = {v}" for k, v in named.items()]
    out += [".sfx_record_at", "    EQUB " + ", ".join(f"&{v:02X}" for v in at), ".sfx_records"]
    out += ["    EQUB " + ", ".join(str(b) for b in r) for r in records]
    out += [".env_att", "    EQUB " + ", ".join(map(str, att3)),
            "    EQUB " + ", ".join(map(str, att2)), "ASSERT ENV_TWO = 32"]
    Path(sys.argv[2]).write_text("\n".join(out) + "\n")
    Path(sys.argv[3]).write_text(json.dumps({
        "effects": effects, "att3": att3, "att2": att2, "tone_att": tone_att, "lock": LOCK_VBLS,
        "field": FIELD, "ym_clock": YM_CLOCK, "via_hz": VIA_HZ}, indent=1) + "\n")


if __name__ == "__main__":
    main()
