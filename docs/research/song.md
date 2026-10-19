# The title song, both ways, on the SN76489

Decision 5 leaves the title song to be chosen by ear: the ST's own sampled
song, or David Lowe's AY arrangement from the Spectrum 128K, converted to
the SN76489. The front end has silent hooks where the ST plays it
(`song_start`, `song_stop` and `song_if_quiet` in `src/front.6502`). This
file renders both as the BBC would play them and gives what each would
cost. It recommends neither: the call is Matt's.

Tags as in the other research files: **[measured]** run or read from the
bytes, with the tool named; **[source]** a link or another file;
**[inferred]** a reading, with what would check it. The figures are the
originals' (their data, their rates) and what the tools below compute from
them, on 2026-10-18.

## Listening

`make song` writes them (it needs `build/st/STAR.PRG` and the Spectrum
128K's tape in `original/zx/`). They're Rainbird's music, so they stay in
`build/`, uncommitted.

| WAV | What it is | Length |
|---|---|---|
| `build/song/st/star.wav` | the ST's song as the ST plays it: 8-bit, 9,830 Hz (`tools/st_samples.py`) | 18.2 s |
| `build/song/wav/st_4096_chip.wav` | the ST's song at 4,096 Hz through one SN channel's sixteen levels | 18.2 s |
| `build/song/wav/st_6144_chip.wav` | the same at 6,144 Hz | 18.2 s |
| `build/song/wav/zx_ay.wav` | David Lowe's tune as the Spectrum 128K plays it, through a model of the AY | 155.9 s |
| `build/song/wav/zx_bass_chip.wav` | the tune converted to the SN, its notes below 122 Hz played by a timer switching the channel's volume | 155.9 s |
| `build/song/wav/zx_octave_chip.wav` | the same, those notes taken up an octave instead | 155.9 s |
| `build/song/wav/*_speaker.wav` | each SN render through jsbeeb's model of a Master's board and its own speaker | |

- **`_chip`** is the SN's output with nothing after it: what the
  conversion makes, as a Master would give it to an amplifier.
  **`_speaker`** is jsbeeb's default output, fitted to recordings of a
  Master 128's own speaker, which lets little through below about 400 Hz.
- Every WAV is scaled to the same peak. On the BBC they wouldn't be
  equally loud: the sample, one channel at period 1, plays about 20 dB
  under the converted tune (the RMS against one tone channel at full
  volume: -20.3 dB at 4,096 Hz, -21.0 at 6,144, against -0.4 for the tune
  with timer bass, +0.3 with octaves, and -1.6 for the AY's own)
  [measured: `tools/songwav.mjs`].
- The tune is one pass. The Spectrum loops it until a key is pressed.

## The figures side by side

| | The ST's song at 4,096 Hz | The ST's song at 6,144 Hz | David Lowe's tune |
|---|---|---|---|
| Heard | the ST's own recording, 18.23 s | the same | David Lowe's arrangement, 155.88 s a pass |
| Data | 37,328 bytes (two samples a byte) | 55,991 bytes | transcribed (as nm's decision 14): the Z80 player's data, 2,171 bytes, and a 6502 player in place of its 635-byte Z80 one. As a stream of SN writes: 40,829 bytes raw with timer bass, 38,583 with octaves; 3,699 and 3,173 deflated |
| On the disc | 146 sectors, 14.6 tracks | 219 sectors, 21.9 tracks | transcribed, its data and player: a dozen sectors or so, in FRONT or beside it [inferred] |
| Streamed | 2,048 bytes a second: a track every 1.25 s, the drive running for each 18-second pass | 3,072 bytes a second: a track every 0.83 s | no stream |
| Loaded for the title instead | about 7 s of reading at the disc's 16K in about 3 s, into banks a game's start must then read back | about 10 s | |
| CPU while it plays | 30.7%, 12,288 cycles a field, at the speech's 150-cycle tick (decision 38); 24% more while a track reads | 46.1%, 18,432 cycles a field; the same while a track reads | a stream player about 260 cycles a field with octaves, 480 with timer bass; a transcribed player perhaps 900-1,500 |
| Interrupts | 82 a field | 123 a field | about 3 ticks a field; with timer bass 2.4 edges a field on average, on a timer a bass channel (two at once in 270 ticks of 23,040) |
| What it loses | the top above 1.9 kHz; sixteen 2 dB levels, the error 10.5 dB under the song below 1 kHz | the top above 2.9 kHz; the error 14.1 dB under it below 1 kHz | the AY's envelope drawn at the tick rate, its noise duller, its bass below 122 Hz either 6 dB quieter or an octave up (below) |

Sources for the table: `tools/mksong.py`'s output for the sizes, rates and
stream; decision 38 for the speech tick's 150 cycles; the journal ("The
disc reader") for 16K in about 3 seconds in jsbeeb; Chuckie Egg 2's
streaming notes for 24% of the CPU while a sector reads
(`../chuckie-egg-2-beeb/docs/streaming.md`, via decision 12);
`docs/research/beeb.md` section 5 for an interrupt's 50 cycles and a chip
write's 36 [measured there]. The stream player's and the transcription's
CPU are [inferred] (below).

## The ST's song

**What it is** (`docs/research/st.md`, "Samples"): `star`, 179,168 signed
8-bit samples, its header saying 10,000 Hz, played by Timer A at 9,830.4 Hz
(data 5), 179,200 bytes (the count and the next 32), 18.23 s [measured].
The ST starts it at each title or credits pass if no sample plays, every
1,101 VBLs, so on the title it plays, rests about 4 s and plays again; it
starts it again after the pilot rating and before the high scores' table
if quiet, so it runs on into the end screen (`docs/research/st-logic.md`,
"The front end") [measured there]. It plays on into the K screen and G's
model viewer, and only a game's start stops it [inferred: neither routine
calls sub_02A30, which a game's start does].

**As the SN plays it** (`tools/mksong.py`):

- Resampled from 9,830.4 Hz by exact ratios, 5:12 to 4,096 Hz and 5:8 to
  6,144 Hz, low-passed at 0.95 of the new Nyquist (1,946 Hz and 2,918 Hz)
  by a windowed sinc, as `tools/mkspeech.py` resamples the speech 2:3.
- Each sample the nearest of the sixteen levels, as `mkspeech.py`'s
  `quantise` makes the speech's: the song scaled to the chip's whole
  range, the error carried to the next. The levels' error against the
  resampled song is 4.2 dB under it in all and 10.5 dB below 1 kHz at
  4,096 Hz; 3.4 dB and 14.1 dB at 6,144 Hz, where the carried error has
  more room above the music [measured: `mksong.py`]. Nothing is cut: the
  title's timing is the whole song.
- Written to tone channel 1 at period 1 as the speech player writes it, a
  sample a tick, and rendered by jsbeeb's own SN76489 (`soundchip.js`),
  resampler and output stages (`audio-output.js`), as its audio worklet
  does (`tools/songwav.mjs`).

Against the ST's own (`star.wav` resampled to 44.1 kHz), spectra taken
every 50 ms up to 2 kHz correlate 0.991 at 4,096 Hz and 0.993 at 6,144 Hz
on average [measured 2026-10-18, a one-off comparison in 48 bands]: what
differs is the noise the levels add and the top they lose.

**What it would cost.**

- **Memory.** Every bank and main RAM are nearly full in play, and FRONT,
  in bank 7 out of play, has less spare than either rate needs (`make
  memory`). Played from memory, the song would take 2.3 or 3.4 banks from
  the game's banks for the title, each read back at a game's start: about
  7 or 10 s more of reading at the disc's measured rate (16K in about
  3 s, the journal's "The disc reader"), on black beside decision 39's
  2-4 s; the song could start as it loads, the read outrunning it
  [inferred]. Streamed, it needs a buffer of at least a track (2,560
  bytes) in what the title leaves free, such as the erase lists in shadow
  RAM, which the game rebuilds at its start (`src/memory.6502`) but G's
  viewer uses, read with ACCCON's X set as code below &3000 may.
- **The disc.** Either rate fits the disc's free tracks as it stands
  (2026-10-18); both wouldn't. A stream reads a track every 1.25 s at
  4,096 Hz and every 0.83 s at 6,144 Hz, each a revolution of reading
  [inferred from the reader's "a track a read"], so the motor never stops
  through the pass: about 18 s of every 22 on the title.
- **The CPU.** The speech's tick is about 150 cycles (decision 38): 30.7%
  of the CPU at 4,096 Hz and 46.1% at 6,144 Hz while the song plays, and
  the disc's NMIs take about 24% more while a track reads [inferred from
  CE2's measured figure]. The title's own work a field is small (the keys
  scanned, the stick, the fades' colours), so the title has the time.
- **Its timing.** Two things hold a tick off on the title [inferred: read
  from `src/front.6502`]: the whole-keyboard scan (`fe_scan`, decision 45)
  runs with interrupts off, about 2,500 cycles a field for 91 keys,
  counted at 27-29 a key: 5 ticks late each field at 4,096 Hz, 8 at
  6,144, which the speech's tick writes late in a burst; and the end
  screen's bands (decision 43) change colour in a line's blank on User
  VIA T2, the speech's timer, every 4 lines, where a tick in the way
  would move a band's change into the line. G's viewer, drawing while it
  plays, would lose the tick's share of its frame.

## David Lowe's tune

The 128K version's tune is David Lowe's (the Spectrum version's credits:
`docs/research/zx.md`). It plays only on the attract screen, after the
menu sits idle about 6 s [measured there].

**The player** (bank 6, &C000-&C27A, 635 bytes of code and variables)
[measured: SkoolKit's disassembly, `tools/zx_song.py`]:

- **The loop** (&C00B) reads the keyboard and calls &C071, which counts
  100 calls down and then moves the tune on a tick (&C083), interrupts
  off. So the tempo is the loop's speed.
- **Channel A** walks a list of pattern numbers (&C0DB); &FF goes back to
  its start. A pattern (through the table at &C533) is a byte the player
  skips, then steps of three bytes: a list's address and a count of ticks
  to wait. The list is register and value pairs to &FF, written as they
  are (&C195). Each step sets A's noise, tone, mixer and envelope: A is
  the drums, and a bass under C's [inferred from its registers].
- **Channels B and C** walk lists of their own (&C178, &C249): a pattern
  number, or &C9, an instrument and then a pattern number. An instrument
  (through &C585) is register and value pairs to &FF, written at once,
  then volumes to &FF. A pattern is notes of three bytes: the period
  (registers 2-3 for B, 4-5 for C) and the ticks it lasts. A note starts
  its instrument's volumes, one written to register 9 or 10 a tick; past
  the last, the volume holds.
- **The mixer is one register**, and each instrument writes all of it, so
  a channel's instrument can turn another's tone or noise on or off. The
  capture keeps that as the Spectrum plays it.

**One pass** [measured: `tools/zx_song.py`, the contended simulator,
the attract screen as the menu reaches it]: 23,040 ticks, 155.88 s, a
tick every 6.766 ms on average (147.80 Hz), from 21,809 to 28,556 T-states
apart as the ULA's contention and the tick's work vary. All three lists go
back to their starts at the same tick, and the next 2,000 ticks repeat the
first exactly. 41,950 AY writes. A tick's work, from &C083 to its return,
is 603 T-states on average and 3,678 at most. The data the player reads,
walked by its rules, is 2,171 bytes in &C27C-&CCB1.

**What it asks of the AY** [measured: `tools/mksong.py`, from the
registers after each tick]:

| Channel | Tone | Below the SN's 122 Hz | Periods | Noise | Envelope |
|---|---|---|---|---|---|
| A | 17,440 ticks | 1,376 | 50-2,025 (2,217-55 Hz) | 19,024 ticks, 13,424 of them with its tone | every tick |
| B | 17,820 | 0 | 36-804 (3,079-138 Hz) | 7 | none |
| C | 16,088 | 6,724 | 20-1,703 (5,542-65 Hz) | none | none |

- Two channels are below 122 Hz at once in 270 ticks.
- The noise's periods (ticks heard): 1 (128), 2 (9,728), 3 (1,888),
  5 (1,063), 15 (1,360), 31 (4,864): the AY's noise shifting from 110.8 kHz
  down to 3.6 kHz.
- The envelope's shapes (register 13): 0 and 9 (a fall, then silence), 8
  (falls, repeated) and 13 (a rise, then held); its periods 256-7,800, a
  cycle from 37 ms to 1.13 s.

**As the SN plays it** (`tools/mksong.py`), tick by tick, each AY channel
on the SN's tone channel of the same number:

- **Ticks** evenly spaced at the pass's mean, 147.80 Hz, as a VIA timer
  would space them.
- **Periods.** The AY's tone is 1,773,450 / (16 P) Hz, the SN's
  4,000,000 / (32 N), so N = 1.12775 P, rounded: off by 3.6-4.3 cents
  (RMS) on each channel, 34 cents at worst, on C's period 20 (5.5 kHz).
- **Volumes** through ym2sn.py's table, which nm took by ear (its
  decision 16): each AY step a 2 dB step of the SN's, so the AY's 15
  to 1 span 26 dB, where its own levels span 37 dB.
- **The envelope** emulated at the tick: its level computed from its
  shape, its period and the ticks since register 13 was written, and
  written as the channel's volume. Its shortest, period 256, falls in 37 ms,
  5.5 ticks: the AY's sixteen steps become five or six.
- **The noise** is the SN's white noise, as loud as the loudest channel
  the mixer gives it to, at the SN's faster rate (7,812.5 shifts a second)
  for AY periods up to 18 and the slower (3,906.25) above, its control
  written only when its rate changes while heard, as nm's decision 17
  has it. Periods 15 and 31 land close (7.4 and 3.6 kHz); periods 1-5
  (22-111 kHz) are much brighter on the AY. A channel with tone and noise
  both on, which the AY sounds as the two ANDed, becomes the tone on its
  channel and the noise beside it, each at the channel's level: more
  tonal, and louder.
- **Below 122 Hz** (an N past 10 bits), two ways:
  - **Timer bass** (`zx_bass`), as nm's decision 18 plays its bass: the
    channel at period 1, its volume switched on and off every half-cycle
    by a VIA timer, 4 µs a unit of the SN's period N as nm's `bass.6502`
    times it (the AY's half-cycle is 4.511 P µs), so the pitch is within
    2 µs a half-cycle of the AY's. A channel at period 1 gives half the
    swing of a tone at the same volume, so these notes are about 6 dB under
    the same level above 122 Hz (7.0 dB in RMS on a test tone [measured
    2026-10-18]). 18,962 edges a pass, 121.6 a second.
  - **Octaves** (`zx_octave`): the period halved until it fits, as nm did
    first.
- Against the AY's own render, spectra taken every 50 ms from 50 Hz to
  8 kHz correlate 0.94 with timer bass and 0.93 with octaves on average
  [measured 2026-10-18, a one-off comparison in 48 bands]: the conversion
  keeps the tune's shape.

**The AY's own** (`zx_ay.wav`) is the capture's writes at their T-states
through a model of the AY in `tools/songwav.mjs`: tones, a 17-bit noise
fed back from bits 0 and 3, the envelope's sixteen steps a cycle, the
mixer's AND, and the levels `tools/zx_speech.py` uses. Its pitch and
envelope rate match test tones' to within the measurement's 1.25 Hz
[measured 2026-10-18], as do the SN's through jsbeeb.

**What it would cost.**

- **Transcribed**, as nm's decision 14 runs David Whittaker's driver: the
  tune's data, 2,171 bytes (its periods converted when the build makes
  it), and a 6502 player with the envelope, the noise and the bass. The
  Z80's tick is 603 T-states on average (170 µs); a 6502 one doing the
  same and the conversion is [inferred] about 300-500 cycles, 900-1,500
  a field, which a transcription would measure. For scale, nm's David
  Whittaker driver and its conversion take about 2,500 cycles a 50 Hz
  frame [measured in nm's decision 14]. Its room: FRONT has less spare
  than the data needs (`make memory`), so room made in FRONT or what the
  title leaves free.
- **As a stream** of SN writes (`mksong.py`'s `stream_bytes`: per tick a
  byte of counts, then the writes; a bass channel its period and level
  where they change): 40,829 bytes raw with timer bass, 38,583 with
  octaves, 3,699 and 3,173 deflated, as a guide to what a packer would
  make of it. Its player: an interrupt a tick (50 cycles) and a chip write
  a byte (36), and with timer bass an interrupt and a write an edge:
  about 480 cycles a field, 260 with octaves [inferred from beeb.md's
  measured unit costs; 1.18 and 1.09 bytes a tick on average, 11 at most].
- **Timers.** The tick wants one, as the speech's does; timer bass a timer
  a channel, two at once. Out of play User VIA T1 runs the palette split
  (`src/engine.6502`), System VIA T1 the effects' tick (`src/sound.6502`),
  User VIA T2 the end screen's bands (`src/front.6502`); the game doesn't
  use System VIA T2.
- **Its timing on the title.** The key scan's 2,500 cycles with interrupts
  off delays a tick by up to 1.3 ms, a fifth of a tick, and a bass edge
  as much, a sixth of its 7.7 ms half-cycle at the lowest note; nm's
  decision 18 keeps its music's frame interruptible for that reason.
- **Length.** A pass is 8.5 times the ST's song. The ST's
  `song_if_quiet` restarts the song at each title or credits pass once it
  has ended; with this tune it would end after about seven, if it isn't
  looped as the Spectrum loops it.

## Not rendered

- **The sample on all three channels**, as the ST plays its own on the YM:
  about 5.9 bits where one channel gives 2.6 (`beeb.md`, section 5), 9.5 dB
  louder, three writes a sample instead of one.
- **The tune's envelope faster than the tick**, for the short falls.
- **Bass from the periodic noise** clocked by tone 2: the noise channel
  and tone 2 are both in use most of the time here.

## The tools

| Tool | What it does |
|---|---|
| `tools/zx_song.py` | Runs the 128K's attract screen on the contended simulator, stops at each of the tune's ticks and logs one pass of AY writes, checked to repeat; walks the tune's data as the player reads it (`build/zx/song.json`) |
| `tools/mksong.py` | The ST's song resampled and quantised at 4,096 and 6,144 Hz, the tune converted to the SN both ways, as timed chip writes; the costs and the tune's register use (`build/song/*.json`, `costs.json`) |
| `tools/songwav.mjs` | Renders each through jsbeeb's SN76489, resampler and output stages, and the AY's writes through a model of the AY (`build/song/wav`) |
