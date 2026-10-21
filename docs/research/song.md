# The title song, both ways, on the SN76489

Decision 5 leaves the title song to be chosen by ear: the ST's own sampled
song, or David Lowe's AY arrangement from the Spectrum 128K, converted to
the SN76489. The front end has silent hooks where the ST plays it
(`song_start`, `song_stop` and `song_if_quiet` in `src/front.6502`). This
file renders both as the BBC would play them and gives what each would
cost. It recommended neither: the call was Matt's, who on 2026-10-21
chose David Lowe's tune with timer bass (`zx_bass_chip.wav`). The last
section, "On the disc", is what was built and how it's checked.

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

## On the disc

Built 2026-10-21 (decision 5, decisions 56-61), with the figures of that
day [measured: the tools named, on jsbeeb's Master].

**What it is.**

- **SONG** (`src/song.6502`), a file of its own, read beside FRONT into
  main RAM's lists' and objects' memory, which nothing uses out of play
  but the silo's two records (decision 56). Its player is the Z80's,
  routine for routine, each variable named after the Z80's address,
  playing the tune's own data: `tools/mksongdata.py` takes bank 6's bytes
  from the capture, walks them by the player's rules as `zx_song.py`
  does, and writes them as 6502 source, each pointer a label, each other
  byte the Spectrum's (`build/gen/song.6502`, 2,210 bytes). One catch:
  list C's last two bytes, &1C and &FF, are the pattern table's entry 0,
  which no list names.
- The conversion is `mksong.py`'s `zx_bass`, at each tick from the
  player's copy of the AY's registers (decision 61): the period scaled by
  SONG_K, ym2sn.py's volumes, the envelope's steps counted a tick at a
  time, the noise at the SN's two rates. The build makes the constants
  and checks them exact against the model for every period the tune has
  and every tick of two passes.
- **The interrupt's part** (`src/song_irq.6502`, below &3000): the tick,
  on System VIA T1 at 6,766 µs, its work with interrupts on and ACCCON's
  X clear (decision 60); the bass's edges, channel C on System VIA T2 and
  channel A on User VIA T2 (decision 58), each one-shot started again at
  its edge for the next half-cycle less its lateness, the first a
  half-cycle from its tick's moment. On the end screen, whose bands have
  User VIA T2, A's low notes go up an octave.
- **The hooks** are the ST's, in FRONT: `song_if_quiet` at each title
  and credits pass and before the high scores' table, `song_start` after
  the pilot rating, `song_stop` at a game's start. The tune goes round as
  the Spectrum's does (decision 59). No effect starts while it plays, as
  the ST's `sfx_start` doesn't while its song, a sample, plays (decision
  57).

**How it's checked** (`make tune`, in `make check`):

- `tools/songcheck.mjs` boots the disc to its title and plays the song
  for a pass and 2,000 ticks into the next. After every tick the
  player's AY registers 0-13, and whether register 13 was written, are
  the capture's, all 25,040 ticks. The chip as the disc wrote it is
  `tools/songmodel.py`'s record of `mksong.py`'s conversion after every
  tick: each channel's period and attenuation, a bass channel's period 1
  and its half-cycle and level, the noise's control and attenuation and
  how often the tick wrote the control; all 25,040.
- The edges: 18,963 in the pass against the model's 18,962, and 228 more
  between a run's last tick and the tick's work stopping it. Each from
  its due moment (its tick's, then a half-cycle on from the last edge's):
  -1.5 µs at the median, 150 µs late at the 99th percentile, 250 µs at
  worst. The tick: 147.798 Hz, each tick within 2 µs (the count's read)
  of 6,766 µs from the last.
- With the bands taking A's timer, 6,000 ticks: A's low notes (1,232
  ticks of them) are `convert`'s octaves.
- The envelope's level for each of its sixteen shapes at 80 steps, most
  of which the tune never reaches, is `mksong.py`'s `envelope`'s.
- The pass as the chip took it is rendered through jsbeeb's SN as
  `tools/songwav.mjs` renders the model (`build/tune/wav/disc_chip.wav`),
  and compared with `zx_bass_chip.wav` by `tools/songcompare.py`: spectra
  every 50 ms in 48 bands from 50 Hz to 8 kHz correlate 0.9975 on
  average, 0.991 at the 1st percentile, 0.829 at worst; the loudness
  -0.5 dB against the model's -0.4 (RMS against one tone channel at full
  volume, songwav's).

**What it costs.**

- On the title: the tick's interrupts 3,026 cycles a field (1,025 a tick,
  the work 915 on average), the bass's 609 (253 an edge, 2.40 a field):
  9.1% of the CPU. Interrupts off at most 436 µs at a time, at the song's
  start; the key scan's chunks 83 µs (the scan 4,065 cycles a field,
  where the whole keyboard with interrupts off was about 2,600).
- Its read: 14 sectors; 0.6 s more before the title at the start, 0.46 s
  more after Esc, none at a game's end (`tools/frontcheck.mjs`). The
  title's unpacking and fade take 41 fields, 37 before.
- Memory: SONG 3,531 bytes of the lists' and objects' 3,550; the
  interrupt's part and its state in main RAM, below &3000.
- On the end screen, C's edges and the tick move 3.65% of the bands'
  colour changes more than 12 µs into their lines, 0.54% by more than a
  line, 162.5 µs at worst; without the song none moves more than 6.5 µs
  (measured with a scratch harness, decision 58).

**Not heard here.** Real hardware: the edges' timing and the chip's
taking of each byte are jsbeeb's.

## The tools

| Tool | What it does |
|---|---|
| `tools/zx_song.py` | Runs the 128K's attract screen on the contended simulator, stops at each of the tune's ticks and logs one pass of AY writes, checked to repeat; walks the tune's data as the player reads it, and keeps bank 6's bytes (`build/zx/song.json`) |
| `tools/mksong.py` | The ST's song resampled and quantised at 4,096 and 6,144 Hz, the tune converted to the SN both ways, as timed chip writes; the costs and the tune's register use (`build/song/*.json`, `costs.json`); its `convert` also records each tick's state, plays on into the loop, and takes the bass channel by channel |
| `tools/songwav.mjs` | Renders each through jsbeeb's SN76489, resampler and output stages, and the AY's writes through a model of the AY (`build/song/wav`) |
| `tools/mksongdata.py` | The disc's tune: bank 6's data as the player reads it, as 6502 source, and the conversion's constants, checked against `mksong.py` (`build/gen/song.6502`) |
| `tools/songmodel.py` | `mksong.py`'s conversion tick by tick, a pass and 2,000 ticks more, and with channel A's octaves, for the check (`build/tune/model.json`) |
| `tools/songcheck.mjs` | The disc's song on jsbeeb against the capture and the model, tick by tick, its edges and its tick timed, and its cost (`build/tune/disc.json`) |
| `tools/songcompare.py` | The disc's render against the model's: spectra and loudness |
