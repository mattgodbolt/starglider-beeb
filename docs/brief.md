# Starglider for the BBC Master 128: a project brief

*Written on 2026-10-17, before the port began, and kept as it was. The
research behind it is in `docs/research/`, one file per machine, with the
tools in `tools/`.*

A brief for porting *Starglider* (Argonaut Software, Rainbird, 1986) to
the BBC Master 128, with Argonaut's blessing, run the way *Chuckie Egg 2*
and *Ninja Massacre* were (`../porting-to-the-beeb.md`).

How to read the tags:

- **[measured]**: we ran it or read the bytes on 2026-10-17; the tool or
  file is named in the research file cited.
- **[source]**: a published source says so; the link is in the research.
- **[inferred]**: our reading or arithmetic. Check it before relying on it.

Addresses are each original's own (the ST's are offsets into STAR.PRG's
text segment), in `&` hex.

---

## In short

- **The original is the Atari ST version**, Argonaut's own, "Completed,
  Sept 1986". It runs headless in Hatari (built in `../hatari`), so it can
  be the port's oracle as the Spectrum was for the earlier ports.
- **Every 8-bit version was a remake, and slow.** Realtime's Spectrum and
  CPC versions and Solid Image's C64 one each run at about **6 fps**
  [measured], with simpler models of their own. The ST averages **13.5
  fps** in flight [measured]. No 8-bit machine has had the ST's game.
- **The ethos is the ST's look:** colour wireframe, one colour an object,
  each object's back faces culled but objects see-through to one another
  (the manual's "Enhanced Vision System"). Filled polygons would break
  the fiction as well as the frame rate.
- **The BBC side is tight but plausible.** A Master draws a short edge in
  MODE 1 in about 800 cycles [measured, jsbeeb]. Estimates put a typical
  ST flight scene at around 10 fps on the Master [inferred], well above
  every 8-bit version and near the ST. The first job is to measure that
  on real ST scenes before the design is fixed.
- **It fits, but for the title song.** Code, the ST's shapes (about 16K
  packed losslessly), the world, the tables and the speech fit a Master
  128 beside a double-buffered screen. The 18-second sampled title song
  does not fit beside the game.

Recommendations for the first decisions (section 3): the ST as the
specification (D1); its wireframe as it is (D2); MODE 1 at the ST's own
320 x 200 geometry, double-buffered in shadow RAM (D3); a fixed game step
at the ST's mean frame time (D4); speech at 4-6kHz, and the title song
chosen by ear (D5); keyboard and analogue joystick (D6); a Master 128,
one disc (D7).

---

## 1. What the original is

### Facts

| | |
|---|---|
| Title | *Starglider*, Rainbird (BT's label), 1986 [source] |
| Who | Argonaut Software: "StarGlider, (c)1986 Argonaut Software Ltd., by Jez San. Published by BT Rainbird, London, UK. Completed, Sept 1986." [measured: STAR.PRG's strings]. Music David Lowe; speech Clare Edgeley; the novella James Follett [source] |
| Kind | A first-person combat flight game over the planet Novenia: a 100 x 100-sector wrapping world of ground and air enemies, energy towers to refuel from, silos to dock in, missiles you steer with a camera, and the StarGlider One to bring down [measured: st.md] |
| Reception | Crash Smash (97%), Sinclair User Classic, Amstrad Action Mastergame; Crash readers' Best Game Overall 1986 [source: Spectrum Computing]. The C64 version: "far slower ... particularly ugly" [source: Centre for Computing History] |
| BBC/Acorn | Never released; no announcement found (web search, 2026-10-17) |
| Existing work | No published source, disassembly or remake found (web, archive.org, 2026-10-17) |

### Every version

| | Atari ST | Amiga | ZX Spectrum 128K | Amstrad CPC | C64 / Apple II |
|---|---|---|---|---|---|
| By | Argonaut (the original) | Argonaut | Realtime Games | Realtime Games | Solid Image (C. M. Wong) |
| CPU | 68000, 8MHz | 68000 | Z80, 3.5MHz | Z80, 4MHz (3.3 effective) | 6502, 1MHz |
| Screen | low res 320 x 200, 16 colours | | 256 x 192, attributes | MODE 1 cut to 256 x 192, 4 colours | multicolour bitmap / HGR |
| 3D view | 288 x 119 | | 240 x 120 | 256 x 128 | 144 x 128 (C64), 252 x 128 (Apple) |
| Buffering | two screens, swapped | | one buffer, copied by the frame interrupt | two screens, R12 flip | two, flipped |
| View colours | one colour an object, 12 in use | | one ink a cell, the last line's | 3 + black, a colour an edge | |
| Shapes | 28 (524 vertices, 802 edges), 7 animated | | 33, 21 of them the ST's rebuilt | 33, the Spectrum's recoloured | 27, simpler re-models |
| Hidden lines | each object's back faces culled; objects see-through | | the same | the same | the same (by screen winding) |
| Frame rate | **13.5 fps** in flight (2-6 VBLs); 9 near the towers; 25 docked | not measured | **6.1 fps** (7.3-11.8 frames a pass) | **6.1 fps** quiet, 3.1 fighting | **6.4 fps** (C64), 10 empty |
| Sound | sampled title song (18.2 s), 4 speech clips, 24 YM effects | `Sglider.snd`, 178,274 bytes: the size of the ST's song | AY tune (attract only), 4 speech clips that stop the game, AY effects | AY effects only | |
| Research | `research/st.md` | `tools/adf.py` lists it | `research/zx.md` | `research/cpc.md` | `research/6502.md` |

All of it [measured] in the research files named, except the Amiga's
(its disc listed only) and the CPU clocks [source].

Three things stand out:

- **Only the ST and Amiga are Argonaut's game.** The 8-bit versions were
  rebuilt by other studios with their own models, maths and, on the CPC,
  their own missions [measured: zx.md, cpc.md, 6502.md].
- **The 8-bit versions all spent their time on maths, not lines.** The
  CPC spends 2.6 ms of a 160 ms update drawing lines and 22.7 ms
  multiplying [measured: cpc.md]; the C64's line drawer is 7% of its
  frame, its projection 21% and redrawing static instruments 11%
  [measured: 6502.md]; a Spectrum object costs 57,000-310,000 T-states,
  mostly maths [measured: zx.md].
- **All of them cull each object's back faces, and none lets one object
  hide another.** That is the original's look, not a cut.

### Getting them

`make fetch` downloads every version into `original/` and checks it
against `SHA256SUMS` (`original/README.md`). Nothing from the originals
is committed. The ST's clean TOSEC image keeps its copy protection and
halts in an emulator; the protected master (`.stx`) boots in Hatari
[measured: st.md].

### Rights (only what is public)

Argonaut wrote the ST and Amiga code; Realtime Games wrote the Spectrum,
CPC and PC versions and Solid Image the C64 and Apple II, each for
Rainbird [source]. So Argonaut's blessing plainly covers the original
the port transcribes. The speech (Clare Edgeley) and the title song
(David Lowe) were made for Rainbird; whether the blessing reaches them is
worth asking [inferred].

---

## 2. The ST, as the port needs it

Everything here is from `research/st.md` [measured] unless tagged.

### What's in STAR.PRG

One 310,054-byte program holds everything but the two pictures:

| What | Bytes | On the BBC [inferred] |
|---|---|---|
| Code, with its strings and small tables | 44,022 (30,166 of instructions reached) | 6502 is less dense for 16- and 32-bit work; plan on 30-40K |
| Per-type tables (shapes, boxes, damage, scores) | 728 | the same |
| Shapes: 28, with 3,040 animation-frame vertices | 34,328 | **about 16K, losslessly** (below) |
| Sine (4096 steps a turn) and arctan tables | 14,342 | 1-2K at a resolution the 6502 can use |
| Fonts and small bitmaps | 3,840 | the MOS font, or the ST's 8 x 8 |
| Four level layouts (82, 89, 97, 114 objects) | 3,264 | the same |
| Samples: four speech clips and the title song | 206,336 | section 3, D5 |
| TITLE.TRA, RESULT.TRA (the title, the cockpit) | 32,144 each | converted to MODE 1 and packed |

**The shapes pack well.** Every coordinate is a multiple of 32, and with a
scale per shape every shape but one fits signed bytes exactly: 3,564
vertices at 3 bytes (10.7K), 802 edges at 2 (1.6K) and the faces as byte
lists (3.6K). The exception is the energy beam (four vertices, with
coordinates up to 32,000), which stays 16-bit [measured: `tools/st_shapes.py --json`,
2026-10-17].

### How a frame works

The game runs flat out: draw, read keys, fly, run every object's handler,
step the animations, test collisions, then wait for the raster past line
192 and swap screens. **Everything moves per frame**, so the ST's game
speed follows its frame rate: 25 fps docked, 13.5 in flight, 9 near the
towers [measured].

Drawing a frame: clear the 288 x 119 window (17,136 bytes); rotate the
nearby objects into camera space; for each object in view, build its
matrix, cull its faces by their normals, transform the marked vertices,
clip each edge at z = 2, project (x' = 128x/z + 143, y' = 128y/z + 68),
clip to the window, and OR a Bresenham line into the bitplanes in the
object's colour. No depth sort is needed, because every line is ORed.
Then the ground dots, the scanner, the waveforms, the laser bolts and
the messages.

### The game

- **The world** is a 65,536-unit torus of 100 x 100 sectors (16-bit
  coordinates that wrap); 140 object slots of 64 bytes, ten kept for
  missiles; four layouts, chosen by level, each tower expanding to three
  towers and a beam.
- **The level** rises each time the score's ten-thousands digit changes,
  to 34; the world is then repopulated from that level's layout.
- **The player** has energy (drained by speed, refilled by flying through
  a beam), shields (refilled in a silo; lost scraping the ground, to
  enemy fire, mines and ramming) and laser energy; two missiles at most,
  steered from their own view.
- **Enemies** are handled by type: walkers and stompers (lasers can't
  hurt them), fighters that turn towards you and fire, tanks, Juno
  cannons and launchers that fire missiles, mines that explode near you,
  homing missiles, and StarGlider One, which only a missile can hurt.
  Enemy fire is an instant hit; the background flashes.
- **Silos**: fly in at the right heading to dock; the tunnel; refuel and
  rearm; Interrogate shows the 17 known objects spinning, with their
  descriptions.
- **Random numbers** mix in the player's steering, so play depends on
  input.

### The sound

| Clip | Bytes | Rate | Length | Plays |
|---|---|---|---|---|
| clare1-4 (speech) | 27,136 together | 6,144 Hz | 0.94-1.21 s each | missile launched, docked and rearmed, shields low and energy low (every 128 frames) |
| star (the title song) | 179,200 | 9,830 Hz | 18.2 s | the title, looped, and the end screen |

All 8-bit, through the YM's three volume registers from MFP Timer A. In
play, 24 effects on the YM. No tune plays in the game [measured].

---

## 3. Decisions to make first

### D1. Which version is the specification

| | (a) The ST | (b) The Spectrum 128K | (c) The CPC |
|---|---|---|---|
| Whose | Argonaut's | Realtime's | Realtime's |
| Models | 28, 7 animated | 33, rebuilt on a coarser grid | the Spectrum's |
| Speed it reached | 13.5 fps | 6.1 fps | 6.1 fps |
| Transcription | 68000 to 6502: the logic and data transcribed, the maths re-done for 8 bits | Z80 to 6502, instruction by instruction, as CE2 and nm were | the same |
| Oracle | Hatari, headless (`tools/st_hatari.py`) | SkoolKit (`tools/zx.py`) | Caprice32 (`tools/cpc_emu.py`) |

**Recommendation: (a).** It is the game the blessing is for, the
complete one (all its models and animations, the speech and the song),
and the only one that ran at a decent speed. The 8-bit versions show what
not to do: they each ran at 6 fps by doing their maths the slow way
[measured]. A Master can do better with the ST's own models.

What (a) costs: a 68000 program can't be transcribed instruction by
instruction. The proposal is **"exact where the game decides,
approximate where it only draws"**:

- **The game's logic is transcribed exactly**: the 16-bit world, the
  handlers, speeds, timers, random numbers, collision boxes, scores and
  levels, with 16- and 32-bit arithmetic on the 6502 where the ST uses
  it. Pass-by-pass checks against Hatari can then compare the object
  table byte for byte, as `make passes` did for CE2.
- **The rendering is free to be the BBC's**: the vertices as bytes, the
  matrices and the projection at the precision the screen needs,
  compared with the ST's projected lines to within a pixel.
- Where the logic reads the rendering (the draw list's camera-space
  positions, the laser's hit test on projected boxes), those few objects
  are computed at the ST's precision.

### D2. The wireframe: the ethos

| | (a) The ST's | (b) All edges | (c) Filled |
|---|---|---|---|
| Look | each object culls its own back faces; objects see-through to each other; ORed colours combine where lines cross | every edge, as the manual's "translucent" fiction might suggest | Starglider 2's look |
| Cost | culling roughly halves the edges; on the BBC, cull by each face's winding on screen (two multiplies a face) [inferred] | about twice the lines | fills cost far more than lines; the frame rate would fall |

**Recommendation: (a).** It's what every version did, and what the
manual's "translucent display of anything within its visual range, even
if objects are behind solid buildings" describes: objects behind
buildings show through.

Drawing with OR, as the ST does, and erasing each buffer by redrawing its
previous lines in black (or zeroing the bytes they touched) gives the
ST's look exactly. EOR, as Elite does, costs the same but leaves a black
pixel where two lines of the same colour cross [inferred: beeb.md]. So no
decision is needed: OR it is, unless measurement says otherwise.

### D3. Screen mode, geometry and colour

The ST's low res and the BBC's MODE 1 have the same pixel: both clock 320
pixels a line at 8MHz (about 40 µs) with one scan line a pixel row
[source: ST timing references; the BBC's MODE 1]. **So a 320 x 200 MODE 1
screen shows the ST's picture at the ST's own size and proportions**, and
the ST's coordinates (the view at 16-303 x 10-128, the projection centre,
the scanner, the gauges) carry over as they are [inferred: check by
showing RESULT.TRA in both].

| | (a) MODE 1, 320 x 200 | (b) MODE 2, 160 x 200 | (c) MODE 4, 320 x 200 | (d) MODE 1, 256 x 192 (as the CPC) |
|---|---|---|---|---|
| Colours in the view | black + 3, any of the BBC's 8 | black + 7 (+ flashing) | 1 | black + 3 |
| The ST's 12 object colours | grouped into 3 | each to its nearest | none | grouped into 3 |
| Detail | the ST's | half across: lines twice as coarse | the ST's | 64 pixels narrower than the ST's view |
| Screen bytes, each of two | 16,000 | 16,000 | 8,000 | 12,288 |
| A short edge [measured: beeb.md] | ~824 c | ~985 c (raster.s, 128 wide) | ~826 c | ~824 c |
| Clearing the whole view [inferred] | 8,568 bytes: ~44,000 c | ~44,000 c | ~22,000 c | 8,192 bytes: ~42,000 c |

**Recommendation: (a)**, double-buffered with both screens at the same
address in main and shadow RAM (draw with ACCCON's X, show with D, flip
at VSync: beeb.md section 2). The view's three colours are a choice to
make with pictures: the ST's colours fall into reds (red, orange, yellow,
pink), blues (two cyans, a teal and four blues) and white. Red, cyan and white
is one obvious set; yellow, cyan and magenta another. The cockpit takes
its own four colours from a palette split at the view's bottom edge, and
the ST's "colour 0 flashes" (hit, mine, refuelling) are one palette
write. A VideoNuLA could later give each group the ST's exact shade.

### D4. The pace of the game

The ST steps its game once per rendered frame, so it plays faster when
there's less to draw. A Master will draw most scenes more slowly than the
ST [inferred], so that rule would slow the whole game down.

| | (a) As the ST: a step per frame | (b) A fixed step at the ST's mean |
|---|---|---|
| Speed | slower than the ST wherever the Master is slower | the ST's average speed everywhere (3.69 VBLs a step in flight [measured]) |
| Look | every step drawn | frames dropped when the scene is heavy |
| Checks | step by step against Hatari | the same, step by step |

**Recommendation: (b)**, as nm's decision 12 did: port the decision (the
game was tuned at its usual pace), not the accident (busy scenes slowed
everything). The step could be 4 VBLs (12.5 a second), or a VIA timer at
3.69. Docked, the ST ran at 25 fps; whether the tunnel keeps a faster
step is a detail for later.

### D5. Sound

**Effects**: the ST's 24 YM effects, each transcribed to the SN76489
(the chips are alike but for the YM's envelopes and noise mixing; nm's
lessons apply).

**Speech** (four clips, about 1 s each) costs CPU while it plays, from a
User VIA timer interrupt [measured: beeb.md]:

| | 6kHz, 4-bit packed | 4kHz, 4-bit packed | Exile's 1-bit runs | None |
|---|---|---|---|---|
| Memory | ~13.5K | ~9K | ~3K | 0 |
| CPU while speaking | ~32% | ~21% | a few % | 0 |
| Quality | near the ST's 6kHz | muffled | voice only | (the Spectrum 48K had none) |

The Spectrum 128K stopped its game for each phrase [measured: zx.md]; the
ST and the Master needn't.

**The title song** (18.2 s at 9.8kHz) doesn't fit beside the game:

| | Memory | Notes |
|---|---|---|
| (a) Sampled at 4-6kHz, loaded for the title only | 36-56K | fills the sideways banks; the game's data loads after it, and again after each game's end screen |
| (b) Sampled, streamed from disc as it plays | a few K of buffer | CE2's streaming reader and scarybeasts' sampstream show it works; any length and rate the disc can feed |
| (c) David Lowe's AY arrangement from the Spectrum 128K, converted to the SN | ~3K | the earlier ports' route; a tune, not the vocal |
| (d) (c) on the title, with a sampled phrase over it | ~3K + a clip | |

Recommendation: speech at 6kHz if the frame rate holds, else 4kHz;
for the song, listen to (a) and (c) side by side before choosing.

### D6. Controls

The ST steers with the mouse (proportional bank and climb; the right
button and mouse for speed; the left button fires) or with keys. The
Master has a keyboard, an analogue port (proportional, like the mouse),
and can take an AMX mouse on the user port.

**Recommendation:** the ST's keys and the analogue joystick first; the
AMX mouse later if wanted.

### D7. Machine, memory and disc

- **A Master 128 only**: the code uses the 65C12's instructions, shadow
  RAM and the four sideways banks. A Model B edition would be a separate
  project.
- **Memory** [inferred: beeb.md]: two 16,000-byte screens leave about 95K
  for everything else: about 10.7K of low RAM, 8K of HAZEL, 4K of ANDY,
  4K beside each screen and 64K of sideways RAM, one bank paged at a
  time. Drawing code and its tables in low RAM and HAZEL (never paged);
  shapes, game logic and speech in sideways banks.
- **One disc**: DFS, single-sided 80 tracks is enough unless the song is
  streamed.

### D8. Variants, for later

- **A 6502 co-processor** (the Master's internal Turbo, 4MHz): Elite's
  split, the maths and game on the co-processor and the lines on the
  host. It pays when the maths is at least about 30% of the frame
  [inferred: beeb.md], which every 8-bit version suggests it is.
  Recommendation: keep that seam in the design (logic and transform, then
  a list of lines), and decide once the single-processor version runs.
- **VideoNuLA**: the ST's exact colours for the three groups, no drawing
  changes.

---

## 4. What a Master can afford

From `research/beeb.md`; cycles are 2MHz, 39,936 to a 50Hz field.

| | Figure | |
|---|---|---|
| A short (4-40 px, about 21 px) edge, MODE 1 | ~824 cycles (178 before the first pixel) | [measured, jsbeeb] |
| A long edge | ~30.6 cycles a pixel | [measured] |
| Erase by redraw | the cost of the lines again | [measured] |
| Full clear | 5.13 cycles a byte | [measured] |
| A sample from a timer interrupt | 86 cycles (105 packed) | [measured] |
| Memory beside two 16,000-byte screens | ~95K | [inferred] |

**Work per frame on the ST** (to come from Hatari: lines, pixels,
vertices and objects per frame in each situation; see section 6).

**A frame on the Master** [inferred, to be measured]: say a flight
scene draws 6 objects, 60 vertices and 50 edges. At about 4,000 cycles
an object (matrix, position), 900 a vertex (transform, cull, project)
and 1,650 an edge (draw and erase), plus about 30,000 for the handlers,
dots, scanner and gauges, that's about 190,000 cycles: 4.8 fields, so
**10 fps** once a frame is rounded up to whole fields. The ST averaged 13.5 fps; the 8-bit versions 6.

---

## 5. The oracles

1. **The ST, headless in Hatari** (`tools/st_hatari.py`): scripted keys,
   screenshots, the debugger. For each step, dump the 140 object records
   and the player's variables; the port's must match byte for byte (D1).
   Inputs and random numbers must be shared: the ST's generator mixes in
   the mouse accumulator, so the port's input is fed to both.
2. **The ST's lines**: a breakpoint on the line drawer (&09128) records
   every clipped line a frame; the port draws the same scene and its
   lines are compared within a pixel.
3. **The ST's routines run alone**: a 68000 core in Python (Unicorn has
   one) can call the matrix builder, the bearing (arctan), the handlers
   and the projection with chosen inputs, as SkoolKit ran CE2's room
   drawer. This tests the transcribed maths exhaustively.
4. **Speed on real scenes**: scenes captured from Hatari (the object
   table at a frame) are drawn by the port's renderer in jsbeeb, timed
   with `frametime`-style counters. This is the first experiment.
5. **The 8-bit versions** run headless too (`tools/zx.py`,
   `tools/cpc_emu.py`), for comparing how they cut corners.

---

## 6. Risks and unknowns

- **The frame rate** is an estimate. It's the project's biggest risk and
  the first thing to measure (section 7).
- **Precision**: byte vertices and 8-bit-friendly matrices must still
  draw the ST's models without visible wobble; the logic's exactness
  depends on computing the few logic-relevant projections at the ST's
  precision.
- **Speech in play** takes a quarter to a third of the CPU while it
  plays.
- **The cockpit in four colours**: RESULT.TRA uses all sixteen; it needs
  converting, perhaps with the dithers of Eben's 2048 and lander.
- **Shadow RAM flips** are trusted from jsbeeb and the port kit; real
  hardware should be checked early.
- **Open in the ST's research** (`st.md`, "Open questions"): the
  sound-effect routines, the gauges, the pilot rating, part of the level
  set-up, names for five unnamed types.

---

## 7. A plan in layers

From the method's order (screen, data, drawing, player, monsters,
objects, sound, front end, loader), with the riskiest first:

0. **A speed spike**: the ST's shapes repacked (`tools/mkshapes.py`), a
   renderer (transform, cull, project, clip, line) in a throwaway build,
   drawing scenes captured from Hatari; measure cycles per frame. This
   settles D3 and D4 with numbers.
1. **The screen**: MODE 1 at 320 x 200, double-buffered in shadow RAM;
   the cockpit converted; the palette split.
2. **The data**: shapes, layouts, per-type tables, sine and arctan
   tables, the font.
3. **Drawing, first seen as the Interrogate screen**: the 17 objects
   spinning, as the ST shows them. It exercises the whole renderer
   without the game, and the ST can show the same object at the same
   angles for comparison.
4. **Flight**: the player's movement, the ground dots, the scanner, the
   gauges; the first pass-by-pass checks against Hatari.
5. **The world**: the layouts, the handlers, lasers, enemy fire,
   missiles, explosions, collisions, levels.
6. **Silos**: docking, the tunnel, rearming, refuelling at the beams.
7. **Sound**: effects, then speech.
8. **The front end**: the title, credits, keys, the end screen's rating,
   the high scores.
9. **The loader and the disc.**

## 8. First concrete steps

1. Copy the harness and build from nm and CE2: `tools/asm.sh`,
   `beeb.mjs`, `play.mjs`, the Makefile's targets, CI with baron pinned.
2. `tools/st_hatari.py`: capture a corpus of scenes (the object table and
   the line list per frame) from the situations already measured.
3. `tools/mkshapes.py`: the ST's shapes to the byte format, checked by
   re-rendering them against `st_shapes.py`'s pictures.
4. The speed spike (layer 0), and its figures back into D3 and D4.
