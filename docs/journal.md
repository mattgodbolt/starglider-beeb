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

### The logic's inventory and framework

Seven agents read the ST's logic range by range into an inventory
(`docs/research/st-logic.md`, with `st-logic.json`). It lists every
routine, variable, object field, table and quirk an exact transcription
must keep, and corrects the earlier research in many places. Some
corrections matter a great deal:
- the post-frame tests settle the ram damage, the energy drain and the
  ground scrape after the screen swap;
- each energy tower becomes a group of six records;
- the free-record stack holds every exploded object, not only missiles;
- random8 adds its caller's d0, which at some call sites is a value left
  over from earlier work: the gunsight's blit at the dots, the previous
  slot's handler at a mine.

Then the framework to check a transcription against the ST, routine by
routine:
- `tools/st_steps.py` dumps the state the logic keeps at every boundary
  of the frame loop, and logs every random number call with its d0 and
  its caller.
- Each port variable's declaration carries `{ST address kind}`, and the
  object table gains the fields only the logic reads, in ANDY.
  `tools/stmap.py` reads the map.
- `tools/logicrun.mjs` puts the ST's state at a routine's entry into the
  port, runs the port's routine, and compares everything the map holds
  with the ST's state at its exit.

The first routines match the ST exactly in every variable and field over
93 frames of flight: random8 and random32, animate_shapes (which now
drives the disc's models too), and player_flight with its missile view
and sight, the d0 it leaves included. A deliberately corrupted capture is
caught.

The memory map for the logic followed from the object table. The fields
only the logic reads come to about 2.8K, which main RAM can't hold beside
the drawing, so they and the logic's variables live in ANDY. ANDY shows
over the first 4K of whichever bank is paged, so the logic's code lives
from &9000 up in two banks: the world bank (5) for what reads the sine
table, and a logic bank (6) for the rest. The list phase stays below
&9000 and runs with ANDY paged out.

The rest of the logic is with five agents: world_render's logic (the
ground dots' respawning among it), the keys and commands, the object
handlers, collisions with the frame's end and the post-frame tests, and
the level change with the new game. Each writes captures for its own
branches.

### Loading

Matt suggested `*SRLOAD`'s Q option, which loads through main RAM. In
jsbeeb it nearly halved the time from `*EXEC !BOOT` to SG starting, from
34.0 seconds to 21.8. But the `*SRLOAD`s were still most of the boot:
without them SG started 4.6 seconds in, while `*LOAD` brought in the 16K
cockpit in about 1.8 seconds.

So `!BOOT` now sets the mode and palette and runs SG, which loads the
rest with the game's own reader, a track a read: HAZEL's files straight
into HAZEL (the filing system's workspace until then), the shapes and the
world into their banks, the cockpit into the screen. The first frame now
comes 10.35 seconds after `*EXEC !BOOT`, where the `*SRLOAD`s gave 36.1
without Q and about 23 with it. The staging of HAZEL's files in bank 7 is
gone. `tools/disccheck.mjs` checks every file the start loads, byte for
byte, as it lands, and the background read after it.

It makes the boot depend on the game's reader, which so far has only run
in jsbeeb (as CE2's has); a real Master is the test that counts.

### The optimisation pass

Five agents worked on the renderer, each in its own worktree and owning
one area: the list phase, each object's set-up, the vertices and the
projection, the faces and the window clip, and drawing and erasing lines.
Each was gated by `make check` and a byte allowance, and none could change
a decision's terms. All five branches merged, with conflicts only where
main had moved on since they started:
- the sine table has to stay above &9000 for the logic, where the lists
  branch had moved it to &8400;
- the lines branch's overflow clear wiped the whole screen, cockpit and
  all, and now clears the window.

Mean cycles a frame, `make spike`, before and after:

| | Flight | The towers | The silo tunnel |
|---|---|---|---|
| A step's list phase (camera and lists) | 57,900 → 34,600 | 42,300 → 16,100 | 10,900 → 1,300 |
| A frame's objects and lines | 166,700 → 108,100 | 292,200 → 181,200 | 214,600 → 136,800 |
| Erasing | 15,800 → 8,300 | 40,000 → 20,200 | 61,400 → 45,700 |

The drawing is unchanged to the pixel on every captured frame, and the
lists and the exactly rotated positions are still exact. The main moves:
- **The list phase.** The camera is built only when the player turns.
  Both rotations chain patched jumps through only the terms the matrix
  has, with the signs fixed at the camera's set-up. Column y is skipped
  while dy is small, and the coarse scan tests a single high byte.
- **Each object's set-up.** Ground matrices are kept while the camera
  holds its pitch, and the products are cheaper.
- **The vertices and projection.** Far vertices go straight from the
  centre's quarters; the transforms skip zero terms.
- **Faces and clipping.** Cheaper face tests, and the edge loops count
  down.
- **Lines.** The erase lists hold each line's set-up, so the erase skips
  it, and they take 3K of shadow RAM where they took 4.4K.

All five agents pushed their branches to GitHub. Matt's "commit and push"
message during the run had reached them, though the brief said not to
push. Once the branches were merged, those copies were deleted.

With logic of about 20,000 cycles a step on top of the list phase, a
frame in flight now comes to about 9 a second at the ST's pace, against
its 12.5. The agents left ideas for a second round. Some need decisions
(erasing small objects by clearing their boxes, leaving y' out of the
approximate rotation, 8-bit products for far objects); most don't.

### The keys and commands

`read_keys` (`src/logic/keys.6502`) is the ST's &0270E: one command a step
from the latch the ST's keyboard interrupt fills (`key_latch`), through
the ST's own scancode table, or else the flight keys held (`key_state`)
into the accumulators. The port's input is the ST's, two arrays the
keyboard layer will fill (decision 6). Everything the ST's commands do
is there: F, M, N, P, Q, S, L with its missile view and the ground dots
kept, the launch from the tunnel's end with its two random numbers thrown
away, I in flight, and the cheat prompt. Three things a command enters
are later layers, stubbed: the Interrogate screen, the waits for keys in
the cheat prompt (which return no key until the keyboard layer comes, so
the prompt ends at its first test), and Esc to the title.

Two captures check it beside the flight's: `steps_keys_cmds` (in
flight, with cheat mode and the K screen's keys written before the
capture starts, so that no write lands inside a checked routine) and
`steps_keys_docked` (teleported into a silo with no missiles, through
the tunnel, the launch and L and P after it). On both, every variable
and field the map holds matches. Things learned on the way:

- **Q first.** Under EmuTOS the first sound effect stops the keyboard's
  interrupts for good (`docs/research/st-logic.md`), so both captures
  turn the sound off before anything plays one, and S comes last.
- **The cheat prompt blocks inside `read_keys`**, so the keys typed at it
  arrive between the capture's two points. Holding Z, pressing Delete,
  then releasing Z and pressing it again gives the prompt its key with
  the key states as they were, which the check compares. The prompt's
  other paths were checked once, outside the captures, with the waits
  returning the keys typed (J S space A R G twice, then J and a wrong
  key): they match but for the last key, still held.
- **Interrogate is frames of its own**: an ad hoc capture of one session
  (I, two spaces, E) ran 216 frames inside `read_keys`, each with
  `animate_shapes` and `frame_end`, and draw_shape overwrote `$1CE/$1D0`
  (the heading's sine and cosine, which `player_flight` recomputes). Its
  layer must run those in each of its frames.

### A baron curiosity, and its issue

Merging the keys part broke the spike's build with a warning that `rot_d`,
the rotations' input, was an input to the harness's entry. Nothing the
keys code ran touched it. The warning came and went as unrelated code
moved, even when only dead code was removed. The cause was in baron:
it matches its control-flow annotations (`ZA_CANJUMP` and the rest) to
their jumps by address alone. Banks 5 and 6 share addresses, so a jump in
bank 6 that landed at the address of one of the rotations' annotated
jumps in bank 5 took on that jump's targets, and with them the rotation
code's read of `rot_d`.

Rich had already opened the issue for `ZA_CANCALL`
(waitingforvsync/baron#29), where it can silently overlap zero page. A
25-line reproduction for `ZA_CANJUMP`, showing an edge added rather than
lost, went there as a comment. Until it's fixed, the logic bank's code
starts past the world bank's list phase, where the rotations' annotated
jumps are (`world_list_end` in `src/banks.6502`). Any annotated jump
elsewhere in the banks needs the same care.

### The object handlers

`object_handlers` (the ST's &07A54) and every handler its table reaches
are in `src/logic/handlers.6502`, in the world bank beside the sine
table, with `angle_to_player` (&08390) and its arctan tables. `make
logic` checks them against the flight capture and seven captures of
their own, 701 frames in all, with every variable and field the map
holds the same as the ST's, and d0 too. Between them they reach every
branch the game can take but two: an enemy's laser at camera z 0, and
the count of hits taken carrying past 255.

- **The table is the ST's.** `tools/mkhandlers.py` reads the 62 handler
  pointers at &08252 and names the port's routine for each, so the five
  places where the second half differs from the first come from the ST's
  data. It also takes the arctan tables, the guns' heights, the missiles'
  heading flips, speeds and lives, and the lasers' damage off level 1,
  which is the same for every type and so a constant (it asserts that).
  The arctan tables are odd about their centres over every entry the
  lookup reaches, so only their upper halves are kept; the tool checks
  each entry.
- **d0 is followed through every handler.** A mine that goes off calls
  random8, which adds whatever d0 the slots before it left. In the mines
  capture it was 7, an earlier wanderer's `r & &F`, and the port matched
  it. The harness compares d0 at the routine's exit, which checks the
  whole chain.
- **The free stack** holds slots. Its count ($25C) and the ST's pointer
  past its top ($9C) are one byte in the port: a new map kind, `index`,
  turns the pointer into an entry number and back.
- **angle_to_player's edges**: dx = 0 divides by zero, which EmuTOS's
  vector 5 returns from with d1 unchanged, so the "quotient" is the
  dividend's low word; dz = -32768 takes table B (the signed compare of
  the neg.w values) and overflows there for small dx. The frozen capture
  puts the player at a Juno cannon's x and at a fighter's with dz =
  -32768, and checks both.

The captures teleport the player (and set the level, the freeze, the
docked flag, counts and types) with Hatari's `w` between steps; the
rarest draws (a beam going out, 1 step in 2048) were made likely by
turning 51 far objects into beams. A coverage run of the port's code
(jsbeeb's instruction hook, every branch both ways) showed what each
capture still missed. What
the ST draws or prints from here, the enemies' laser lines and the
mines' messages, isn't in the port yet: the logic runs in steps, the
drawing in frames, and the two need a way to meet.

### world_render's logic

world_render (&04FE8) decides as well as draws, and its logic is now the
port's, in two halves round the frame's drawing (decision 14):
`world_lists` (the level-up test, the score add from the $D4 mailbox, the
camera, the ground dots, the launch's count and the docked tunnel, the
lists) and `world_after` (the draw loop's matrix cache, the laser). Both
match the ST in everything the map holds on the flight capture and seven
captures of their own (`tests/st/steps_world_*.txt`): the tower group's
beam switched by the laser, a kill crossing 10,000 on level 34, the
tunnel's pick-up, refill and launch, the cheat's refill, the missile
view, the sight on a word's edge, and a target the laser can't hurt.

- **The dots' d0.** random8 adds whatever d0 holds, and at the dots
  that's the drawing's: the gunsight's blit leaves its last word, which
  depends only on the sight's x mod 16 (the table is the bitmap's, checked
  for every shift), a projected dot leaves the projection's shift, a
  respawn its own random word, and the missile view the window's step.
- **The cone's decision is exact, and cheaper than rotating every dot.**
  As decision 11 does for objects, a dot is rotated approximately, and
  exactly only within the approximation's bound of the cone's edges. The
  approximation is the dots' own: the ground's column of the matrix exact
  (its dy is every dot's), the other two by products of signed bytes, each
  entry and offset / 128 rounded, read from the quarter-square tables as
  f(q + e) - f(q - e), with a bound per dot. And a dot found surely in view
  keeps its decision, unrotated, while a margin lasts: each frame takes off
  the most the camera's move and turn can have shifted the cone's tests
  for a dot that far away (in six distance classes), and its place must
  not have changed. On the flight capture, of 40 dots a frame 17.8 are
  rotated and 2.8 of those exactly, and the dots cost about 35K cycles a
  step, from 58K rotating each with the list phase's rotate_approx
  (measured 2026-10-18). A bound per dot from its own running distance,
  not its class's, would leave about 12 a frame to rotate (modelled).
- **The drawing's leftovers.** The draw loop's object matrices leave the
  last one built's sines in the logic's trig_sin and trig_cos, and a
  matrix is built only when an object's angles differ from the last's
  ($180-$184), so the port keeps that cache too.
- **The harness.** The lists are in the map now (a `list` kind: the ST's
  pointer and count), so world_after starts from the ST's draw list and
  world_lists' lists are checked; the camera-space positions of objects
  rotated approximately are checked as `tools/scenecheck.py` checks them;
  the key states are inputs, put but not compared, since the ST's
  keyboard interrupt writes them mid-frame; `world_whole` runs both halves
  for the missile view, which has no lists point; `--cycles` times a
  routine.

### The logic's parts together

The keys, the handlers and world_render's logic, each transcribed on its
own branch, are merged. Three things had to give:

- **One port variable for each of the ST's.** The branches had each
  declared the ST variables they used, so `shields`, `missiles` and
  `m_iris` came twice, and the laser's fire keys, the cheat and the
  pending score each had two names for one ST address. Each was put from
  the ST's state and so passed, but code writing one would never have fed
  code reading the other. Each now has one, and `tools/stmap.py` refuses
  any ST byte two port variables hold (but for a copy marked `also`, as
  `anim_s10` is).
- **The world bank was full.** The laser's half of world_render's logic
  (`world_after`: the draw loop's matrices and the player's laser) moved
  to the logic bank, `src/logic/laser.6502`, reached from the world bank
  by `logic_bank_call`, and itself reaching `sincos` by `world_call`. The
  dots' exact rotation lost its `rotate_abs` (the optimisation pass's
  `rotate_exact` takes d offset already).
- **The capture scripts' own writes.** To keep the player alive or set a
  scene up, scripts write the ST's memory through Hatari's debugger, and
  the write lands wherever the ST is. The beams capture refills the
  shields, which mostly lands in world_render, and with the world check
  run on it the ST seemed to fill the shields there. `tools/st_steps.py`
  now echoes a POKE after each write, the frame lists the points it
  landed before, and `tools/logicrun.mjs` leaves out (and counts) any
  routine's run with a write inside it. The captures were made again,
  four at a time (`STEPS_JOBS`): the scripts time their keys in seconds,
  and seventeen at once slowed each enough to halve what they caught.
- **Drawn is the draw list.** The harness let an approximately rotated
  object off only if the ST hadn't drawn it, by the record's drawn flag.
  The silo's two records keep what TOS left in theirs, so the tunnel,
  docked by a script in the missile view, behind the camera, seemed
  drawn. It asks the ST's draw list now.

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

### The renderer's second round

A second pass over the objects phase, with nothing a decision covers
changed: each scene's lines, lists and exact positions are the same on
every frame as before it. The objects phase's mean fell 8.2% in flight,
9.8% at the towers and 6.2% docked (99,226, 163,400 and 128,303 cycles,
measured 2026-10-18). What paid:

- each vertex's outcode made once (`v_code`), so an edge is rejected
  before its ends are copied, and one wholly inside goes straight to
  accept; the line drawer's ends aliased to the clipper's;
- the vertex transforms folding 4t into their start when every axis has
  room, so the general case only shifts; a near object wholly in front of
  the near plane takes a path with no z tests;
- faces settled first by the products of |c|'s high bytes, with a bound
  from the low bytes; a zero matrix entry scaled without its products;
  the scaled matrix kept while an object's matrix and scale are the last
  one's; `far_setup` skipping a term whose A_z is 0;
- `sdiv32` a byte at a time (checked against the 68000's divs on 20,308
  divisions, overflows included);
- the workspace's vertex arrays and marks first, page-aligned, so no
  indexed read crosses a page; `stamp` in fixed zero page, as it lasts
  from frame to frame, and `erase_init` wiping the marks, which hold the
  disc's catalogue and the cockpit's pages before the first frame.

What didn't: skipping zero terms in the general vertex (worth a few
hundred cycles a frame for about a hundred bytes HAZEL hasn't got);
stopping the division early (the docked scene's quotients are nearly all
14-15 bits); kmul shortcuts (81 of 2,160 calls in flight); placing hot
branches off page boundaries, which the disc's layout wouldn't keep.
Baron's zero page pool now peaks in the drawing, a few bytes short of
the MOS's &FC.

### Every routine on every capture

With the level change and the new game in, every routine runs on every
capture: 14 routines on 25 captures, each frame's state put from the ST's
at the routine's entry and compared at its exit, all matching (checked
2026-10-18). Getting there turned up three things.

- **The scripts' writes go in at a known place.** The echo that marked a
  `debug w` reached the log out of order with the points' own output, so
  it placed a write only to the nearest frame. Once a capture is armed, a
  `debug w` is now taken as the frame branch's `poke`: it runs from a
  breakpoint at world_render's entry, just after `top`, and tags the
  frame's order through the same channel as the points.
- **The new game empties the draw loop's matrix cache**, which the level
  branch hadn't seen. The ST writes &FFFF to the pitch's twice and the
  roll's once, never the heading's, and the port does the same.
- **The handlers' dispatch moved to main RAM**, so the logic bank's code
  can pass its address (baron#29). Its targets are now generated one by
  one: given as a list symbol, baron resolved their labels only in main
  RAM's own section (waitingforvsync/baron#30), and every handler
  seemed unreachable. A list assignment referring forward to a label
  also failed to settle (waitingforvsync/baron#31).

### Nine calls

The transcription and the optimisation rounds left nine places where the
port would do something the ST doesn't, or where the ST leaves the choice
open. They went to Matt as one page, each with its options, figures and a
recommendation, and Matt took every recommendation (2026-10-18):
decisions 15 to 22. One call kept the ST as it is, so it has no number:
each step still clears every object's drawn and near flags below the
slot count, as the ST does, rather than only the last lists' (about 750
cycles a step, against the object table's exact check).

### No y' for the approximated, and B from R's high byte

Decisions 21 and 22 were built and measured on 2026-10-18. Before building
21, the ST's code was searched for every read of an object's camera-space
y (+$2A). There are eight:

- the two draw loops, enemy fire and the player's laser read only objects
  on the draw list, which are always rotated exactly;
- the scanners load y' and overwrite it before using it;
- the collisions read it, but test z and x first, and an approximated
  object is always out of the box on one of those.

So `rotate_approx` now makes only x' and z', and the relevance test asks
only about those. In flight the list phase falls from 28,856 to 25,487
cycles a step on average; steps where the craft is banked or pitched
fall from 56,872 to 49,628, and the worst from 53,419 to 45,426. The same
objects are rotated exactly as before. The approximate path also got its
own way out of the loop: while it joined the exact path, baron took y'
to be read there, and its zero page rose from &F4 to &FA.

Of decision 22's two trims, far objects' B now comes from R's high byte,
rounded: two byte products where proj_x has four. That saves 1,229
cycles a frame in flight and 858 at the towers, about half the estimate,
as the rest of B's set-up stays, and no edge comes to be 2 pixels or more
from the ST's. The room came from moving `kmul` into the world bank, as
only ground_matrix's build calls it, after paging that bank. Dropping
proj_x's lowest product from a shift of 17 failed the silo tunnel: its
long level lines cross the window's bottom edge, where a pixel's change in
height slid one clipped end 16 pixels. From a shift of 18 it would pass,
for 693 cycles in flight, 1,137 at the towers and 136 lost docked, but
it is left out.

| `make spike`, mean a frame | Flight | Towers | Docked |
|---|---|---|---|
| Camera and lists | 34,574 → 31,105 | 16,114 → 15,668 | 1,283 → 1,260 |
| Objects | 99,226 → 97,997 | 163,400 → 162,542 | 128,303 → 128,341 |

### The game on the disc

The disc plays now. After loading, a new game starts at level 1, as the
ST's title starts one, and every step runs the ST's frame in its order
(`src/step.6502`): world_lists, the frame drawn on the last step due,
world_after, read_keys, player_flight, object_handlers, animate_shapes,
collisions, level_message and frame_end's logic, then the post-frame
tests, going on to level_start. At a game over it goes straight to the
next game until the front end is in. The model viewer is gone.

- **A whole step checked.** The spike includes the step too
  (`spike_step`, with the controls and the frame's showing stubbed), and
  `tools/logicrun.mjs`'s `step` runs it from each frame's top to the next
  frame's. Every capture's 2,022 steps match the ST's in everything the
  map holds, level changes included (checked 2026-10-18). So the routines
  are right in the order and the banks the disc runs them in, not only
  one at a time.
- **The frame waits for its logic.** A frame is still drawn between its
  step's lists and logic, but shown only after the logic and
  `view_overlays`, so the enemies' lasers, the mines' messages and the
  bolt go on the frame they belong to (decision 16).
- **The keys** (decision 6) are the ST's. The vertical sync's interrupt
  reads the BBC's matrix into the ST's key states and its one-byte
  latch, as the ST's keyboard interrupt writes them. It reads them only
  when the keyboard's auto-scan has seen a key since the last read, or
  one was held then (the OS's own trigger, CA2): about a hundred cycles a
  field with none held, about 1,100 with one. Where the BBC lacks the
  ST's key, the nearest: COPY for Insert, the Master's keypad RETURN for
  keypad Enter, DELETE for Backspace. The logic never reads Help.
- **The joystick** is the ST's mouse. Each step adds the stick's move
  since the last into the accumulators the mouse moves. Its fire button
  is the mouse's left button (the laser), and the second joystick's is
  the right (while it's held, the stick's climb sets the speed). Its
  travel from centre to either end is the turn's clamp and the climb's,
  so a stick kept within its ends comes back to level flight, and a
  count's move is noise. `tools/inputcheck.mjs` checks the stick, every
  key and both buttons. The Master's ADC is at &FE18, not the Model B's
  &FEC0, which cost a hang at start.
- **Zero page.** On the disc the drawing and the logic share one call
  graph, and the step is a loop. So anything baron thinks a step reads
  before writing is kept from one step to the next, through everything.
  The dots' tests made five such (values made on paths the carry
  chooses), and the pool ran out; discarding them per dot fixed it. They
  were found by discarding every global at the step's top, which fit,
  then every one but one.
- **One mine routine.** The handlers and the collisions had each
  transcribed the mines' proximity (&07B28). The disc reached only the
  handlers' copy, and the build warned of the other as dead code. The
  handler now calls collide.6502's, which flags the mine's text.
- **The cost.** Flying straight at the level's start: 8.5 frames a second
  at 12.6 steps (`make fps`). A step's logic takes about 34,000 cycles,
  three quarters of it object_handlers' walk of the slots, and
  world_lists 36,000. In a hard turn the camera's matrix is full and
  changes every step: world_lists takes 112,000 (the dots 42,000, the
  rotations 49,000) and a step 146,000. The frame rate falls to 2.7, and
  decision 14's cap slows the game to 10.6 steps a second (measured
  2026-10-18, before decision 21's saving in the rotations).

### The panel

Everything the ST draws from the game's state besides the 3D, the
gunsight and the missile view's window is now the port's
(`src/panel.6502`): the top bar, gauges and bank ticks, scanner, bottom
numbers, waveforms, the messages in the view, and colour 0's flash. The
font, strings, positions, scanner colours and waveform frames come from
STAR.PRG at build time (`tools/mkpanel.py`).

- **Only changes are drawn.** The ST redraws all of it every frame. Here
  each screen remembers in ANDY what its panel shows, so a frame in
  flight costs about 11K cycles, and the panel takes the disc from 8.5
  frames a second to 8.0 (measured 2026-10-18).
- **Where the ST draws it.** The gauges, scanner and numbers are drawn
  after the frame's 3D, from the state between the lists and the logic,
  as the ST's waveforms routine draws them. The texts are drawn after the
  step's logic, where the logic's texts exist (decision 16). The docked
  menu's test is post_frame's, which comes after the frame is shown, so
  the panel makes it itself.
- **Texts and lines.** Texts the ST prints before its 3D are ORed in, as
  its lines are ORed over them. Those it prints after are opaque, and
  redrawn each frame they show. The game now starts with LEVEL 1 on
  screen, so erasecheck learned which cells the panel keeps.
- **From bank code.** The panel sets ACCCON's X from the logic's bank,
  reading the objects and lists only with X clear. Its data lives below
  `world_list_end`, where baron#29 forbids code but not data.

It's checked two ways. `make panel` (now part of `make check`) puts each
captured frame into the spike, draws it into alternate screens, and
compares every pixel with a model of the ST's formulas: all 2,125 frames
of the 25 captures match. That model was then checked against the ST
itself. `tools/st_panel.py` captures in Hatari the panel's input and the
screen the ST made, and the model, run in the ST's own colours and plane
operations, matches all 257 frames over the panel's rows and the opaque
texts' cells.

The colours are each ST colour to the nearest of its band's four. The
scanner's dots take their objects' lines' colours, so the white things
are the only blue dots.

### The view besides the objects

The gunsight, the ground dots, the player's bolt, the enemies' laser
lines and the missile view's window are drawn as the ST draws them. The
ST draws the dots, the bolt and the lines from inside its logic. Here the
logic records them instead (which dots `ground_dots` kept in view, that
`player_laser` drew the bolt, each shot's gun and end), in variables the
checks don't map, and the drawing draws from those records. The sight and
the dots go in the draw phase; the bolt and the lines go after the step's
logic, onto the same frame (decision 16).

- **The dots cost the most.** Each one in view is rotated into camera
  space, exactly when it's near and otherwise by a rotation made only for
  the ground, good to a pixel. Then it's projected and plotted as &0976E
  plots it: about 66K cycles a frame in flight (measured 2026-10-18).
- **The missile view's window** is the cockpit picture sliding over the
  view as the ST copies it, a whole character row at a time, since
  m_iris steps by 8. Once open, it's put back after an erase. It lives in
  bank 7 with the code that draws it, which also holds the draw phase's
  other view code, since the panel filled the logic bank. Drawing it
  whole costs about 200K cycles a frame while it slides.

`make view` (now part of `make check`) checks all of it against the ST
on the 25 captures:

- the dots against &047AA run on each capture's state: 95% at the ST's
  pixel, the rest within one, none missing, none stray;
- the sight, the bolt and the shots exactly, the shots' ends from the
  ST's own random numbers replayed;
- the window's whole screen on 449 frames;
- every frame erased back to the cockpit.

With everything in, the disc draws 5.1 frames a second flying straight,
holding 12.5 steps (`make fps`, 2026-10-18): the dots and the panel took
it from 8.5.

Baron#29 struck again in bank 7: with the window's code first, at &9000
below `world_list_end`, the build ran out of zero page for routines that
never meet it. The picture now goes first, so the code starts past the
rotations' chain.

### Eight more calls

Building the flight layer left eight more choices the ST doesn't settle
for a four-colour screen, a different keyboard and a slower machine. They
went to Matt as a second page, and Matt took every recommendation
(2026-10-18): decisions 23 to 30. Matt has no joystick, so the keyboard
is the controls that must feel right. Three change code: the flash
written at the flip (24), the panel's animations per step (25) and every
shot since the last frame (30).

Decisions 24 and 25 are built. Each step's flash leaves its colour
pending, which a later step's black doesn't undo, and the interrupt
writes it to logical 0 as it shows the frame. So a flash on a step whose
frame was dropped still shows, and it lands as the ST's does. The panel
steps the waveforms and the energy bar's dimming once for each frame
count since its last draw (`panel_steps`), the ST's per-frame rule run
for every step, and `make panel`'s model does the same.

### The camera and the rotations in a turn

Holding a hard turn, the camera's matrix is full and changes every step,
and the camera and the rotations took 54,000 cycles of world_lists'
105,000 (measured in jsbeeb on main, 2026-10-18). Now they take 41,000.

- **The approximation on bytes.** Decision 11's approximate rotation makes
  each term from one byte product: the matrix entry to 8 bits (|m| / 64,
  rounded) by the offset's high byte, taken as the middle of the 256
  offsets it stands for. Taking the middle halves the error the high byte
  alone made, which leaves room for the 8-bit entry: within 418 of the
  ST's, where decision 11 allows 444 (`tools/mkrotate.py` derives it). On
  the captures the worst is 238, where it was 408. An object's
  approximation takes 259 cycles, not 395. Column y's offset is mostly
  within 256 of 0 (the ground is flat and the player near it), and then
  its products are the same for every object, so the rows' constants take
  them: one set for a high byte of 0 and one for -1.
- **Only what changed.** In a steady turn the pitch and roll stay. So the
  camera keeps their sines, the products of them alone and the ground
  objects' constants, and makes only the heading's sines and the eleven
  products they're in, through a new entry into build_matrix. A product by
  a sine of 0 or a cosine of 16384, as a level pitch makes most of them, is
  taken as it is (`fmul_trig`). rotate_setup patches only the entries that
  changed (six of nine in a steady turn), and links the chains again only
  when an entry's kind or sign changes. The camera falls from 12,300
  cycles to 6,300.
- **The exact rotation** keeps its four byte products a term, with one
  SEC where there were four (a byte product never borrows) and a carry
  added straight into the next sum: 1,370 cycles, not 1,460.
- **The near box.** The checks call an approximated object near when the
  ST's own x' and z' are within NEAR_BOX, and the port tested its
  approximation against the same box, so any error at that edge could
  fail them. The old approximation's errors fell inward on the captures by
  luck; the new one's didn't, on three flight frames. The near test now
  allows another ROT_SLACK (NEAR_TEST), which rotates 0.3 to 0.4 more
  objects a step exactly.
- **The cost.** Holding a hard turn, world_lists takes 91,500 cycles a
  step (the camera 6,300, the rotations 34,800, the dots 43,300
  untouched): 3.2 frames a second at 11.7 steps. Flying straight, 8.4 at
  12.6 (measured 2026-10-18, before the view's drawing was merged).
- **Baron.** With the logic bank three bytes further on, its `JMP
  (set_ups,X)` sat at the address of a `BMI climbed` in player_flight in
  the world bank. The branch took on the jump's targets (baron#29 reaches
  conditional branches too), and baron warned that the level's set-up
  read init_objects' `record` unset.

Matt can't judge calls like these until the game can be played, so until
then they're Claude's to make (Matt, 2026-10-18), recorded as decisions
like any other, for Matt to revisit. Decisions 31 to 33 are the first:
the rotations' near box and slack, and carrying relevance over.

### The handlers' cost

object_handlers was three quarters of a step's logic: about 25,000 cycles
a step on the disc at level 1's start, 33,000 at most. It is now 18,800,
and 24,200 at most (measured 2026-10-18). With it the disc draws 5.47
frames a second flying straight, holding 12.5 steps (`make fps`, from
5.10). Every routine still matches the ST on every capture.

- **The walk skips what does nothing.** The handler by type is now a gate
  (`tools/mkhandlers.py`): none for the types whose ST handler does
  nothing the port keeps. For the five whose first test is the near or
  draw list's flag, the walk tests the flag itself, so most slots cost no
  call. The call is one JMP (abs,X) in main RAM. The ST clears the homing
  request after every slot; here the three handlers that make one clear
  it, and one left at the start is cleared after the first slot, as the
  ST's is. The walk stops at the slot past its last, made to look
  exploding until then, so only an exploding slot tests for the end.
- **random32 in zero page.** The handlers draw dozens of numbers a step,
  so the walk copies random32's state into zero page for its own copy of
  the routine.
- **angle_to_player's quotient in 8 bits.** Away from dx 0 and the
  -32768s, only the quotient's low byte matters, since from 256 up the
  clamp is decided. So eight steps of shift and subtract make it, instead
  of the 68000's divs. The arctan tables keep their low bytes alone;
  their high bytes are steps, counted by generated code.
- **set_velocity by bytes.** Every speed the game sets is below 512, so
  speed times a sine fits 23 bits, made from two 8-bit products each.

A differential test ran the port's old routines against the new ones from
the same states: the handlers on capture states perturbed with homing
requests, launchers near the player, and random types, flags and
explosions; angle_to_player on every dz for twelve pairs of dx and the
reverse; set_velocity on every heading for every speed from -600 to 600.
No case differed.

Decision 30 is built. The handlers' shot records now last until a frame
draws them, so a frame shows every shot its steps fired, each from the
attacker's place at its own step, and a new game starts with none. There
is room for four a step over a frame's most steps (`SHOTS`, `ASSERT`ed
against `MAX_STEPS`).

### The near box, the slack and carried relevance

Decisions 31 to 33 were built on 2026-10-18.

- **The near box** (31). The checks now call an approximated object near
  when the ST's own x' and z' are within the largest collision box,
  NEAR_BOX, which the build takes from STAR.PRG's box table (the beam's).
  The port tests its approximation one slack wider.
- **The slack** (32) is 444, `ASSERT`ed to cover ROT_BOUND, the most the
  approximation can be off the ST's, which `tools/mkrotate.py` now
  computes from its own derivation. The checks hold the approximation to
  ROT_BOUND rather than the slack, so a slip in the derivation would fail
  them, and `make rot` holds the ST's own matrices to it too. The test's
  edge ahead compares the low byte as well, since the slack is no longer
  a multiple of 256.
- **Carried relevance** (33). An object relevant at the last step is
  rotated exactly at once. For one rotated exactly then, relevant means
  drawn or within NEAR_BOX: an exact position needs no slack. In a hard
  turn 8.9 objects a step are carried, so as many fewer are approximated,
  for 0.2 more exact rotations. The first build kept an object carried
  while the relevance test, run again on its exact result, held. That
  saved less: the test, and a flag on every approximation to tell the
  paths apart, cost more than they kept.
- **Both checks take the carried path.** `scenerun.mjs` carries ob_exact
  from frame to frame, as the disc carries it from step to step. A carried
  path made to skip its rotation fails both.
- **build_matrix's products with the heading** moved to the world bank's
  end (`src/matrix.6502`), past the logic bank's code. build_matrix pages
  that bank for its sines anyway, and it frees about 290 bytes of main
  RAM, the region every layer wants.

A hard turn's rotations fell from 34,700 cycles a step to 31,800 and its
approximations from 40.9 to 32.0 a step; flying straight, 9,900 to 9,700
(measured 2026-10-18). The list phase now ends a few bytes short of the
sine table, which is aligned to 1K: much more code there would move the
table, and everything after it, 1K on.

### The missile view drawn as the ST draws it

The ST was caught in its missile view (`tests/st/missile.txt`).
`tools/st_scenes.py` now sees every frame of it, not only those that make
lists, and `tools/st_render.py` takes the missile's camera there.

- **While the window moves,** opening or closing, the ST draws nothing
  but the cockpit's picture: no lists, no dots, no objects, a frame of 2
  fields.
- **Once it's open,** it makes the lists from the missile's place and
  angles, and draws them clipped to a window of its own, x 80-239 and y
  16-112, the projection's centre still the view's. The model draws every
  line the ST drew there.

The port drew the stale lists over the sliding window, with the player's
angles, clipped to the view's window, so lines crossed the window's
walls and erasing them left holes. Now (`view_objects`):

- **None while it moves.** Once it's open, the missile's place and angles
  stand in for the player's while the objects are drawn, as they do for
  the lists.
- **Its window.** The clip's window was the view's, in its immediates;
  now `clip_window` patches each of them (`CLIP_SITES`) for the view's or
  the missile view's. A window short of x 256 needs x's low byte tested
  against its right edge, which the view's never does: the low byte's
  branch is patched on to the high byte's test, so the view's clip costs
  what it did. On the missile capture's open frames every line is within
  3 pixels of the ST's (`make spike`, which now has the missile scene).
- **The slide.** Drawing the window whole from its runs took about
  200,000 cycles a frame, and the disc drew one frame in two or three of
  the slide's steps. Each screen now remembers which picture row each of
  its window's character rows shows, and draws only the rows that differ:
  a row's sides, its inner window only where it has something in it,
  cleared only where it had. The picture is kept by rows
  (`tools/mkcockpit.py`), in less room than the runs and their put-back
  tables took. The disc now draws a frame every step of the slide, at
  most 101,000 cycles (`tools/missilefps.mjs`, measured 2026-10-18).
- **MISSILE VIEW's holes.** When a text the screen shows is in rows the
  window draws again, those rows are drawn and the text is taken off the
  panel's record (`ps_texts`), so `panel_messages` no longer clears its
  pixels from the picture just drawn.
- **The bar** is drawn a block at a time, and the open window's put-back
  takes 20,000 cycles, not 31,000.

`make view` draws the window over each other step's, over texts and over
an overflowed erase, and checks the objects; `erasecheck` launches and
steers a missile and checks the window after every erase on the disc.
The ST's slide takes 14 of its 2-field frames; the port's takes 14 steps
(decision 4), twice as long.

### The dots made cheaper

The ground dots were the largest single cost in flight: about 61K cycles
a frame to draw and 16K a step to decide flying straight, 42K a step in a
hard turn. Both halves are cheaper, and the decision is still the ST's on
every capture.

- **Kept by its own distance.** A dot surely in view keeps its decision
  while its margin outlasts the drift. The drift's classes went by powers
  of two of the dot's |dx| + |dy| + |dz|, its rotation's part from the most
  any entry moved. Now they go by 1024 units of the dot's own bound (its
  sum, plus half its margin for the camera's moves while it lasts), the
  rotation's part from what each column's change can do to the cone's
  tests. In a hard turn 13 dots a step are worked out, not 23.6.
- **One rotation for both.** The decision took its own approximation,
  with a bound of a hundred or more, and the exact rotation within that of
  the cone's edges. Now it takes the drawing's ground rotation, every term
  of which is within 2 of the ST's floor(m d / 16384) for every entry and
  offset (`tools/groundcheck.py`, which the build runs when the generator
  changes). So the exact rotation is wanted for 0.09 dots a step in a hard
  turn, not 2.5, and the drawing takes each dot ground_dots rotated rather
  than rotating it again. ground_dots makes the rotation, in bank 7 with
  the view's code, only when the camera or the height changes.
- **Carried while the matrix holds.** While the camera's matrix is the
  last frame's, a far dot's camera-space position changes only by the
  matrix's product with the camera's move, so the drawing keeps each
  one's and takes that off. Flying straight hardly a dot is rotated.
- **Their own projection.** A far dot can only be in the window 512 or
  more deep, so its projection skips the shallow cases, tests x and y
  against the depth first, and interpolates the reciprocal between its
  9-bit mantissa's entries, where proj_z takes the mantissa's middle:
  97.6% of the ST's dots at its pixel, from 95.0%.
- **Their own erase list** (decision 29). Each screen keeps its dots' top
  bytes, 2 bytes a dot, and zeroes those and the ones below before it's
  drawn again, rather than a 6-byte line set-up a column on the lines'
  list.

A far dot's height from the ground's plane, decision 29's other half,
was built and measured. It stands in for row y' only for the dots the
drawing rotates itself, which the rest has made few, and making the plane
each time the roll or the height changes takes back about what it saves,
for 0.3% of the dots off the ST's pixel. It is left out.

| On the disc, cycles | Straight | Hard turn |
|---|---|---|
| ground_dots, a step | 15,966 → 8,588 | 42,252 → 28,020 |
| The dots drawn, a frame | 61,059 → 44,131 | 67,698 → 58,428 |
| The erase, a frame | 18,617 → 16,085 | 23,501 → 20,354 |

`make fps`: 5.50 to 6.37 frames a second flying straight, 2.90 to 3.40
held turning (measured 2026-10-18). Bank 7 holds most of the cost, 1.8K of
its window section.

### The sound effects

On 2026-10-18 the ST's 24 effects were read and captured, and the eight
the game starts were put onto the SN76489 (decision 5; decisions 34-36).

- **The capture.** `tools/st_sfx.py` traces every YM register write in
  Hatari, timed to the CPU cycle. The game has its own effect tester at
  &0268A, which nothing calls: each key plays the next effect. The
  capture jumps into it at a frame's end, and sets a breakpoint on the
  tester's call of `sfx_start` before each key, so a script can play any
  effect with any count, alone or close behind another. Under EmuTOS five
  of the six Timer A handlers block the MFP after their first tick
  (st-logic.md's `move.b $DF.l`); writing &DF to that byte gives them the
  intended effect.
- **What they are.** Four noises on all three channels, shaped by the
  YM's own envelope, which lock out every effect for 22 VBLs. Sweeps of
  tone A's period at Timer A's rate: the laser falls from 6.25 kHz to 496
  Hz in a quarter second, and the cheat's and refuelling's are 33 ms
  chirps. Docking alternates two tones. Tone A or the noise sounds, never
  both, and there's no music in play. Effects 4-7 are a broken siren, with
  a working one unreferenced beside it.
- **On the SN.** Both chips make a tone of 125 kHz over its period, so
  tone A's periods go onto tone 0 unchanged. The noise goes on the noise
  channel, clocked by a silent tone 2 at the YM's noise period. The
  envelope's 32 levels become the SN's nearest attenuations, once a
  field, from measurements of an ST's YM: three channels, or two once a
  sweep ending under the noise has put channel A's volume to 0, as the
  capture shows the ST doing. The SN stops 28 dB down, so the last third
  of each noise's fall is silent. The tone sits 6 dB under the noise's
  peak, as one YM channel does against three.
- **Timer A becomes the System VIA's T1,** the OS's centisecond timer,
  free once the game owns the machine. Each effect's start is a record of
  the state it sets and the bytes it writes to the chip, generated from
  STAR.PRG into the logic bank's own first 4K, which only data can use.
- **The fastest sweeps can't tick at the ST's rate.** The vertical sync's
  handler runs longer than the ST's 104 µs ticks, and the VIA's flag
  counts two ticks as one, so effects 8 and 9 take 7 and 8 of the ST's
  ticks a tick, still 37 and 38 steps a chirp (decision 35).
- **The palette split.** A tick in progress when the split's timer ran
  out held the split up, by a line and more: with the laser firing, 23
  fields in 1,499 were late. Now a tick due within 256 µs of the split
  waits for it, the interrupt handles a split that arrived during a tick
  at once, and an effect's start, which writes its record with interrupts
  off, waits for the split to pass. After that, none were late in 2,999
  fields.
- **The samples' count.** Nothing plays speech yet, so `sample_left` never
  fell, and the first warning would have silenced every effect after it.
  `sound_field` counts it down at the speeches' rate until the player
  does it itself, and a sample's start silences an effect, as the ST's
  mixer does. Since the interrupt now changes it, the logic reads its
  four bytes with interrupts held off, as the 68000 reads it in one.
- **The check** (`make sfx`, in `make check`) plays the capture's 35
  plays into the disc's `sfx_start` at their moments and compares the
  chip's writes with the ST's converted: 556 changes matched in value,
  order and time.

The sound's interrupt costs about 120 cycles a field while a noise sounds
and about 220 a tick: with the laser held, 1.8% of the CPU (measured
2026-10-18).

### The objects erased by their boxes

Decision 20 is built. The erase was measured first (`tools/eraseprof.mjs`,
30 seconds a run): flying straight it took 14,159 cycles a frame. Of that,
drawing the objects' lines again took 9,135 (3.2 objects a frame, 13
lines each, 219 cycles a line), the dots 2,326, the gunsight 1,527, the
bolt and the shots 530, and the list itself 471. In a hard turn it took
16,616, the objects' share 11,059.

- **The box.** Each vertex an object draws goes into the object's box:
  the columns and lines it lies in within the window. A vertex past the
  window records the edges it's past (from its outcode), and the box goes
  out to those edges, where the lines are cut. An object that may cross
  the near plane gets no box: its cut ends can land anywhere, and an
  object that near is seldom small.
- **The choice.** Once the object is drawn, box_end (`src/box.6502`, bank
  7) gives up its entries for a single box entry when (H + 3)(W + 3) is
  under 64 n - 27 for its n lines. On the four scenes that is within 2% of
  choosing each object's cheaper erase by its measured costs. In flight
  99% of objects are boxed; the silo tunnel's long lines are not.
- **The clear.** line_go sends the box's code to erase_box, which clears
  each character row's part a column at a time with eight unrolled STZ
  abs,X.
- **The reach.** The box relies on a far object's vertices being inside
  the window whenever far_setup says the object is, and they weren't
  always. The first-order matrix can put a vertex up to sqrt(1 +
  (X0/128)^2) radii (on the screen) from the centre, so on the missile
  capture three edges ran a pixel onto the cockpit's frame, and drawing
  them again as zeros cut holes in the picture. The reach is now pq (1 +
  |X0|/256), which bounds that anywhere in the window, and those edges are
  clipped as the ST clips them.
- **The missile view.** A box lies within the clip's window, so it never
  clears the window's walls. erasecheck checks every frame of the view.

| On the disc, a frame | Straight | Hard turn |
|---|---|---|
| The erase | 14,159 → 6,517 | 16,616 → 7,371 |
| … the objects' part | 9,135 → 1,644 | 11,059 → 2,060 |
| Every step drawn: the erase | 10,626 → 5,798 | 16,954 → 7,006 |
| … the objects' drawing | 105,821 → 109,582 | 155,829 → 160,462 |
| … the two together | -1,075 | -5,303 |

The model's erase came true. What it left out is the bookkeeping on the
drawing side: about 50 cycles a vertex to take it into its box and 250 an
object to decide and log the box, plus the reach's own few hundred a
frame. That takes back about three quarters of the erase's fall flying
straight and half of it in a turn (measured 2026-10-18). The reach makes
a larger saving possible, untried yet: a far object whose reach lies
wholly outside the window can be skipped before its vertices are made.

### The speech

Clare Edgeley's four clips, resampled 2:3 to 4,096 Hz (decision 37) and
packed two levels a byte, run through bank 7's first 4K, the logic bank's
after the effects' tables, and bank 7's window section's tail; each
clip's trailing near-silence is cut, which is what fits the tail. The
player ticks on User VIA T2, its count reloaded for what it overran, a
late tick's debt taken off the next. While a clip plays IRQ1V is the
speech's own: a short entry in main RAM pages bank 7 for the tick.

- **A read race.** The tick read the count's low byte, then its high byte
  a few microseconds later, a wrap behind whenever the low byte passed 0
  in between, and every tick that waited out the palette split hit it:
  each clip's samples after it came a period early. A new test, that the
  samples' line stays steady from field to field, fails on every clip
  without the fix.
- **A call across banks.** The docking speech, in the world bank, called
  `speech`, which the effects' work had moved into the logic bank: with
  the sound on it would have run whatever sat at that address in the
  world bank. No capture docks with the sound on, so the logic check never
  met it. It goes by `logic_bank_call` now.
- **The cost.** A clip takes 45-48% of the CPU (decision 38): with a
  warning repeating, 5.9 frames a second against 6.4; with clips back to
  back, the frame loop sits at its step cap and the game slows by a
  quarter while they last (measured 2026-10-18).

`make speech`, in `make check`, checks every clip's levels against the
packed ones, the rate, each sample's time, the line's steadiness, the
clip's end at the ST's length, a clip with a key held, `sample_stop`, and
that the split is never late; it writes WAVs to listen to. The disc's
check makes its read in play itself now, beside a clip, and puts back
what it overwrote: the game no longer reads in the background.

### Room in main RAM, and far objects skipped

Main RAM's resident code had 211 bytes free with the speech in. An audit
found most of what was there had to be there: the interrupt and
everything it touches, the code that switches banks between calls, the
routines code in several banks shares, and the draw phase. The rest
moved.

- **The start.** What SG runs once (the disc reader made ready, the
  loads, the set-ups, the game's opening state) is now SG's second part,
  `start.6502`, after the resident code. It may run on over the lists and
  objects, which nothing uses until `play` clears the objects and starts
  the game, so it costs the resident code nothing.
- **The banks.** Bank 7 took the screens' copy and the window's clear,
  which set X. The world bank took what only its code uses: the handlers'
  random numbers, `fmul15`, the animation lists, and `ground_camera`,
  whose bank switch moved to its caller. The shapes bank took the
  type-to-shape table and the draw phase's helpers that run only with it
  paged.
- **The result.** Free main RAM went from 211 to 1,462 bytes; the world
  bank, bank 7 and the shapes bank gave 338, 137 and 233 bytes.
- **The far objects.** A far object whose reach lies wholly outside the
  window is now skipped once its radius is read, before its matrix. Past
  FAR_C_MAX the reach is pq(1 + |c|/128), which can find an object outside
  but never inside. Most of the objects that drew nothing were out there:
  in flight, 400 of the 422 clipped ones.
- **Measured.** `make spike`'s lines are unchanged. The objects' cost fell
  19% in flight and in the missile capture, and 3% at the towers. The disc
  went from 6.40 to 7.60 frames a second flying straight, and from 3.42 to
  3.67 holding a turn (measured 2026-10-18).

### The speech's tick in main RAM

Decision 38 left the speech's tick in bank 7, behind an entry in main RAM
that paged it in and out. With the room made in main RAM, the tick moved
there whole, below &3000 with its entry. It pages a bank only for the
byte a first sample reads; the clips stay where they were.

- **What a tick needs from the last** is in the code it runs. Which
  sample comes next is a branch each sample sets, so a clip's end byte is
  tested only when it's read. A tick on time needs no guard on its count's
  high byte, as its low byte is never near its wrap; only a late tick
  reads the count again.
- **Late ticks.** A late tick used to set the next count to 1 and take
  what it owed off the one after. Beside the disc's NMIs, ticks fired that
  way came one after another for longer than a field: the speech's entry,
  taking T2 first, kept the vertical sync out, and T1 came round to 0 with
  no split due, so the tick waited on its flag for ever. A late tick now
  writes its sample and those it owes in the same interrupt, handing the
  engine anything waiting between them by pushing a return as an interrupt
  does, so the engine's RTI comes back into the tick. The split's wait
  ends too if T1 passes 0 without its flag.
- **The debt paid exactly.** The old late ticks paid a few microseconds
  short: with a key held, a clip ran at 4,095.7 samples a second against
  4,098.4. `make speech` now holds a clip with a key held to the rate it
  keeps with none.
- **The cost.** A tick takes about 150 cycles, from about 220, so a clip
  takes 30-31% of the CPU, from 45-48%. With a warning repeating the disc
  runs at 7.27 frames a second, against 7.10 before and 7.60 with no
  speech; with clips back to back, 4.27 against 2.77, and the steps at
  12.17 a second against 10.33 (measured 2026-10-18). Main RAM gave 349
  bytes, and fixed zero page's last byte is the tick's.

### The front end

The disc boots to the ST's title: the credits after its wait, the K
screen, Esc back to the title, and the game's end, with the words, the
pilot rating, the high scores and the end screen's colour bands. Each
comes from the ST's code with its timings in VBLs, read and run in Hatari
(`docs/research/st-logic.md`, "The front end"), quirks kept: the place
number never printed, the second score always 0, the high scores lasting
until the machine is switched off.

- **FRONT** holds bank 7 out of play (decision 39) and loads over flight's
  files, never while speech plays. The title is TITLE.TRA dithered into
  four colours and packed (decision 40), shown on the shadow screen so the
  cockpit stays on main RAM's. A game's start loads flight's files back,
  2-4 seconds on black in jsbeeb; the game's end loads FRONT behind the
  ST's own 301-VBL wait.
- **The K screen** asks for the ST's six keys and stores them as pressed;
  they join the key map (decision 44).
- **The title song** isn't in: `song_start`, `song_stop` and
  `song_if_quiet` in `src/front.6502` are silent hooks where the ST calls
  its sample, for Matt to choose by ear (decision 5) between the ST's
  sample streamed (about 37K at 4 kHz, the drive running for each 18-second
  pass) and David Lowe's AY tune from the Spectrum 128K (about 3.2K with
  its player, no streaming).
- **A latent bug.** `erase_init` was part of the start, which the lists
  overwrite once a game has run, so a second game crashed once the merge
  moved the start. It's resident now, and frontcheck plays a game after a
  game's end.

`tools/frontcheck.mjs`, in `make check`, compares every screen byte for
byte with a model of the ST's printer, times the waits, checks the defined
keys reach the logic as the ST's scancodes, and checks the high scores.

