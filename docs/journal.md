# Journal

How the port got here, in order.

## 2026-10-17

### Finding Starglider

With Argonaut's blessing, Matt set out to bring *Starglider* to the BBC
Micro, with the Master 128 as the target. Nothing of it was on disc:
the Argonaut archive (`../Argonaut`) starts in 1998, and its only mention
is a comment in `baseobj.h` saying the class was "based on baseobj base
class for Starglider III".

No BBC or Acorn version was ever released, and no disassembly or source
has been published (web search, 2026-10-17). Every released version was
found on archive.org and Spectrum Computing, and `make fetch` now gets
them all (`original/README.md`):

- **Atari ST**, Argonaut's original, "Completed, Sept 1986". TOSEC's
  clean image, its protected master as STX, and the EMT crack. Its one
  program, `AUTO/STAR.PRG`, holds everything: the code, `SHAPE.DAT`, the
  title song, the sounds and Clare Edgeley's speech.
- **Amiga**, Argonaut's own port.
- **ZX Spectrum** 48K and 128K, **Amstrad CPC** and **IBM PC**, all by
  Realtime Games (Ian Oliver, Graeme Baird).
- **Commodore 64** and **Apple II**, by Solid Image. They are the only
  6502 versions, and were the poorly received ones.

### Five versions, researched side by side

Five agents worked at once, one a machine, each writing
`docs/research/<machine>.md` with its tools in `tools/<machine>_*`:

- **The ST** (`st.md`): Hatari was built from source in `../hatari` with
  EmuTOS, and the protected master boots in it headless
  (`tools/st_hatari.py` drives it through its command FIFO). The clean
  TOSEC image halts at the copy protection. A recursive 68000
  disassembly (`tools/st_disasm.py`, labels in `tools/st_star.ctl`)
  found the frame, the renderer, the shapes, the handlers, the world and
  the samples. The ST averages 12.5-13.5 fps in flight (two runs).
- **The Spectrum 128K** (`zx.md`): nm's `zx.py`, adapted, loads the
  Bleepload tape and flies headless. 6.1 fps.
- **The CPC** (`cpc.md`): a scriptable Caprice32 in `../caprice32`. Also
  6.1 fps, MODE 1 narrowed to 256 x 192.
- **The C64 and Apple II** (`6502.md`): one engine by C. M. Wong for
  both. The C64's frozen backup was resumed on py65 and profiled: 6.4
  fps, its time in maths, a full clear and redrawing the instruments.
- **The Master** (`beeb.md`): line routines timed in jsbeeb per mode
  (about 824 cycles a short MODE 1 edge), clears, the memory beside
  double-buffered screens, and the cost of sampled sound.

Every version culls each object's back faces and none lets one object
hide another, so that is the original's look, which the manual's
"Enhanced Vision System" explains. The 8-bit versions are remakes with
their own models, and all ran at about 6 fps.

A second pass in Hatari counted the ST's work per frame
(`tools/st_workload.py`): in flight about 35 lines of a median 3.3
pixels, 30 vertices drawn and 4 objects. So on the Master the cost will
be set-up per line, vertex and object, not plotting, and a flight scene
costs out at 3-4 fields a frame against the ST's 4 (brief, section 4).

The ST's shapes pack into about 16K losslessly: every coordinate is a
multiple of 32, and with a scale per shape all but the energy beam fit
signed bytes.

### The brief

`docs/brief.md` lays out what the original is and the decisions to make
first, with figures and recommendations: the ST as the specification,
its wireframe as it is, MODE 1 at the ST's own 320 x 200 (the two
machines' pixels are the same size), a fixed game step at the ST's mean
frame time, and the sound options. Its first step is a speed spike on
scenes captured from the ST.

## 2026-10-18

### The decisions, and the renderer modelled

Matt took the brief's recommendations as they stood: decisions 1-8.

Before writing the Master's renderer, the ST's was modelled in Python,
exactly: `tools/st_scenes.py` captures scenes in Hatari (each frame's
variables, the object table and the shape table, then every line the
ST draws, by object), and `tools/st_render.py` rebuilds every line from
the state alone. It matches the ST on every camera-space position, list
and line of three captures (flight, the towers, the silo tunnel), quirks
included: the near clip's doubled fraction and the projection's divide
overflows both show in the tunnel. So the port's renderer can be checked
against the model on any scene, without Hatari.

The capture also measured what the brief had to guess: about 40 objects
pass the coarse test each frame and are rotated into camera space, not
15, because the test keeps the whole band in z whatever x is.

### The speed spike

The renderer was written for the Master (`src/render.6502`, built as
`build/spike` by `make`) and run on every captured frame in jsbeeb
(`make spike`: `tools/mkscene.py` turns a capture into the port's inputs
with the ST's results, `tools/scenerun.mjs` runs and times them,
`tools/scenecheck.py` compares). The first cut followed the ST's
arithmetic throughout and matched it exactly: every list, every
camera-space position and every edge, the tunnel's quirks included. It
took 10-22 fields a frame.

A sampling profiler (`scenerun.mjs --profile`) put half of that in
multiplication and an eighth in division, and under 1% in drawing lines,
as every 8-bit version found. What brought it down, in order:

- the camera rotation the logic reads, still exact, generated per frame
  with the matrix's bytes patched into the table reads, its zero and unit
  entries skipped (`tools/mkrotate.py`);
- the drawing's own maths made approximate (decision 1): a vertex
  transform with the object's scaled matrix patched in and every product
  unsigned (`tools/mkxform.py`), a projection by the reciprocal of the
  depth's mantissa, faces tested by byte-by-word products;
- far objects drawn with their perspective made linear (decision 10);
- the near objects the game can't be deciding about rotated
  approximately (decision 11);
- ground objects' matrices made from their heading alone.

A few wrong turns: the tunnel's lines were up to 16 pixels from the
ST's, which looked like the transform's rounding near the camera, so the
ST's exact arithmetic went back in for near vertices; it changed one
edge. The cause was the reciprocal table's half-step correction, right
for a truncated mantissa and wrong for an exact one, which small depths
have. A loop to patch the rotation (to save memory) cost 5,000 cycles a
frame; patching through fixed offsets from each term got most of that
back.

Where it stands, the renderer alone (the lists and the objects; no
erase, dots, panel or logic yet), against the ST's whole frame:

| Scene | The Master, fields a frame | The ST, VBLs a frame |
|---|---|---|
| Flight | 5.6 mean | 4.0 |
| The towers | 8.2 | 5.5 |
| The silo tunnel | 5.5 | 3.7 |

[measured 2026-10-18, `make spike`]. Every list and every camera-space
position the game reads matches the ST's; of the edges both draw, 99.9%
are within a pixel of the ST's. Memory is full: main RAM, HAZEL (the
multiply and reciprocal tables, the line drawer and the transforms) and
the shapes' bank. So the brief's estimate (3-4 fields in flight) was
optimistic: per-object and per-vertex work costs more than its sums
said.

### The first disc

With the repository on GitHub, the README links a disc to run in jsbeeb,
so the renderer got a disc of its own before the game has one
(`src/main.6502`, `make disc` makes `starglider.ssd`): the ST's models
turning one after another, as its Interrogate screen shows them.

- !BOOT sets the mode and palette through BASIC, puts the shapes and the
  sine table into sideways RAM with `*SRLOAD`, and leaves the files bound
  for HAZEL in screen memory, as the filing system's workspace is in
  HAZEL; the program copies them in and makes no OS call after.
- Both screens are at the same address in main and shadow RAM (decision
  3). ACCCON's X moves every access to &3000-&7FFF, the CPU's own fetches
  too, and the code reaches past &3000, so X is set only around each line
  (`line_plot`) and the screen's clear, which run from HAZEL.
- Each screen keeps the lines drawn into it (in a sideways bank) and
  erases them two frames later by drawing them again as zeros.

The first run left trails on the shadow screen only.
`tools/erasecheck.mjs` (now in `make check`) stops after every erase and
looks at what's left: the shadow screen was erasing the main screen's
lines, because `line_erase` uses X and the frame was still holding the
screen's number in it.

### The step back

Before the agents' optimisation pass, a step back to size the rest of
the game, so the pass works within budgets rather than spending bytes the
game will need. `docs/plan.md` is the result.

- **The ST's frame, profiled.** Hatari's CPU profiler counts cycles at
  every address, but a profile saved through the command FIFO came out
  empty: only entering the debugger processes the data, and remote
  commands never do. A one-line patch to the Hatari in `../hatari`
  processes it on saving. `tools/st_profile.py` runs a profiling script
  (`tests/st/profile_*.txt`) and splits the time by area: in flight 68%
  drawing, 9% ground dots, 9% waiting for the raster, 6% logic, 4%
  printing, 4% panel.
- **The Master's whole frame**, reckoned from that and the measured
  renderer: about 6.5 frames a second at the ST's pace now, about 9 after
  the optimisation pass, against the ST's 12.5.
- **Memory is the harder limit.** The game as the ST has it wants about
  117K on the Master and about 96K is there. A compact sine table, an
  object table of only the fields the port uses, and the front end loaded
  from disc close the gap, just.
- **The co-processor** would bring the ST's speed and end the squeeze, so
  the plan builds the engine around a display list, decision 8's seam,
  with the single-processor game first.

The plan's order: an engine skeleton (the memory map with `ASSERT`ed
budgets, the list and draw phases, the interrupts and the fixed step),
then the agents' pass, then the layers.

Matt's calls on it:

- **No co-processor edition** (decision 8, revised).
- **The disc stays in use** (decision 12). It's a disc game, so it can
  load by phase as Elite does, or stream as Chuckie Egg 2's B edition
  does. CE2S's 1770 reader comes across as it is, and the front end and
  speech come from disc.
- **The object table keeps only what the port uses** (decision 13).
- **Speech at 6kHz**, 4kHz if the memory map can't hold it (decision 5).

With the docked screens, the cockpit picture and the front end loaded
when they're wanted, the plan's map holds about 86K in flight of the
96K, which leaves room to spend on speed.

### The engine skeleton

The plan's first step, built and checked a piece at a time, each commit
keeping `make spike` passing.

- **The sine table** is the ST's first quarter plus a bitmap. The rest
  follows by symmetry, mirrored in the odd quarters and negated as the
  ST's rounding negates (1 - v). The exceptions are 193 entries, each one
  off, with the direction fixed by its quarter. Baron computes both from
  the ST's own formula. It's 2.5K where the table was 10K, for about
  1,600 cycles a frame. `sinecheck` now runs `sincos` itself at all 4,096
  angles.
- **The object table** is an array a field, by slot, in main RAM
  (decision 13). `tools/mkobjects.py` lays it out and writes a map that
  the harness uses to put the ST's records in and read them back.
  Indexing by slot took the list phase from 54K cycles to 48K.
- **The world bank.** The list phase moved into bank 5 beside the sine
  table, where the logic will join it. Main RAM's code fell from 10.6K
  to 5.9K, and bank 6 is free.
- **The frame** (decision 14). The game owns the IRQ, counts fields,
  steps every four, and shows each frame from the next vertical sync.
  Each screen keeps a list of the lines drawn on it in shadow RAM, for
  erasing. The spike now erases between frames and checks that nothing
  is left: nothing is, on every captured frame.

Two things came out of building it. First, the lists are the logic's
input: the ST makes them before its logic and the logic reads them, so a
fixed step has to make them every step. That puts the list phase at 30%
of the CPU at 12.5 steps a second, and makes it the optimisation pass's
first target. Second, the ST's order (lists, drawing, logic) maps onto
the steps if the last step before a frame draws between its lists and
its logic, which needs no copy of anything for the drawing. The model
viewer on the disc runs at 12.5 frames a second (`make fps`).

### The cockpit

While the optimisation pass's agents worked on the renderer, the screen
layer began: the ST's cockpit (RESULT.TRA) on both screens, around the
view's window, with a palette split at the view's bottom edge (decision
3).

- **Four colours from eight shades.** The cockpit is mostly eight blues
  and cyans, plus red, yellow and green lights. The BBC has eight colours
  and no shades, so `tools/mkcockpit.py` ordered-dithers each ST colour
  between the pair of a band's four that mixes nearest it. It renders the
  options as pictures for Matt to choose from (decision 3 left the
  colours open). The disc uses option b for now: the view and its frame
  in black, red, cyan and white, the panel in black, red, cyan and blue.
  That makes the split one logical colour, white to blue: four palette
  writes, which fit one horizontal blank.
- **The split's timing** came from a sweep in jsbeeb.
  `-D SPLIT_SWEEP=n` builds with `n` in place of the adjustment and paints
  scan lines 126-131 whole in logical 3, so a split that lands mid-line
  shows as a line half white and half blue. The clean window was -242 to
  -202 microseconds; -222 is its middle. CE2's constant was five lines
  late here, as its sync is elsewhere. Real hardware may differ:
  something to check on Matt's Master.
- **Steady timing.** MODE 1's interlaced sync puts alternate fields half
  a line apart, which would move the split, so `screen_mode` turns
  interlace off. It also turns off the cursor, which was still showing.
- **Both screens.** `!BOOT` now stages HAZEL's files in bank 7 and loads
  the cockpit into the screen. `start` copies the cockpit to the shadow
  screen a page at a time, and only the window is ever cleared, by code
  below &3000, where ACCCON's X changes nothing.

### The disc reader

Chuckie Egg 2's streaming edition's 1770 reader, its Master half, is now
the game's (`src/disc.6502`, decision 12), with three changes.

- **The NMI routine pages the destination's bank** for each byte and puts
  `bank_now` back, so a load into a bank goes on whatever the game has
  paged. That's why `BANK` writes `bank_now` first.
- **Files are found by name** in the DFS catalogue, which `disc_init`
  reads at start, so nothing depends on where baron puts them.
- **A track a read.** Read a sector at a time, with the next asked for
  from the engine's waits, 16K took 13.75 seconds: the polls come a frame
  apart, so every sector cost a revolution. Now each track is one
  multi-sector read from the first sector wanted, and the NMI routine
  stops it with a Force Interrupt after the last byte wanted. 16K takes
  about 3 seconds, with the game running throughout, a little slower
  while the NMIs take their share. (One slip on the way: CE2's poll
  relies on the carry surviving from the poll into the next read's start,
  to report "busy", and the new track arithmetic broke that.)

Until the game has a file of its own to load, the disc reads SHAPES
again into bank 6, which nothing uses yet, as the models turn.
`tools/disccheck.mjs` runs that with the disc in jsbeeb's drive and
checks every byte. The tools that run the disc without booting now put
it in the drive too (`tools/disc.mjs`). Real hardware is the test that
counts here, as CE2 found: jsbeeb's 1770 is kinder than the chip.

### Collisions and the frame's end

One part of the logic's transcription (decision 1), done beside four
others: collisions (`src/logic/collide.6502`: ramming, the missile's
hits, refuelling, docking, and the mines' proximity, which the mine
handler calls), and the frame's end (`src/logic/frame.6502`:
level_message, frame_end's count and flash, and the post-frame tests:
the speech warnings, the docked texts, ramming's cost, the cheat's
refill, the energy drain and the ground scrape). Each matches the ST in
everything the map holds on the flight capture and on five captures of
its own (`tests/st/steps_collide_*.txt`, `steps_post_warn.txt`). Run
with a branch log in jsbeeb, they take every branch the game can, but an
empty near list and the levels from 16 on; the rest can't be taken (a
test already settled, a count that never gets so high).

- **The near list in the map.** Collisions walk the list the list phase
  made, so the harness now puts the ST's into the port's: a new kind,
  `slotsdown`, for a list pushed downward as the ST pushes it, which the
  port's `near_slots` holds in the order pushed. Walked from its last
  entry, it's the ST's ascending order.
- **Pokes at a fixed point.** A capture that moves the player with the
  debugger's writes changes the state wherever the emulation happens to
  be, so whichever routine spans that moment sees a difference it didn't
  make. `poke` lines now run at the next world_render's entry, just after
  the `top` point, and the harness leaves that frame out for the one
  routine that starts there.
- **Inputs.** The speech warnings wait while a sample plays, and the
  bytes left are counted down by the ST's Timer A interrupt in real time
  between the points. A trailing `in` in a variable's braces gives it to
  the routine but never compares it.
- **The mines** run inside object_handlers, between two points, so the
  capture has two more, at the proximity block's entry and end, which log
  the mine's record (a0) for the harness to call the port's routine with.
- **A quirk kept.** A ram's flag outlives the ram when the next first
  box hit is a beam (refuelling neither sets nor clears it), so the ram
  costs again every frame in the beam: measured, and in
  `docs/research/st-logic.md`.

The ram's cost reads a table by level, and from level 16 on the ST reads
past it; for now the port takes level 15's, which needs a decision.
