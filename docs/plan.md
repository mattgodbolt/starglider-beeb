# After the spike: a plan for the rest of the game

*Written on 2026-10-18, after the speed spike, as the step back before
the renderer's optimisation pass; revised the same day with Matt's calls
(decisions 8, 12 and 13). The tags are the brief's: **[measured]** (run
or read, the tool named), **[source]**, **[inferred]** (reasoning or
arithmetic: check before relying on it).*

## In short

- **The ST's own frame**, profiled in Hatari: in flight 68% of its time
  goes on drawing, 9% on the ground dots, 9% waiting for the raster, 6% on
  the game's logic, 4% on printing the score and messages, 4% on the
  panel [measured: `tools/st_profile.py`].
- **The Master's frame**: the list phase is the game's logic too, so it
  runs every step, 12.5 a second (decision 14), and takes 30% of the CPU
  in flight; a frame's drawing is about 5.3 fields. That's about 5 frames
  a second at the ST's game speed (decision 4); after the optimisation
  pass, about 8. The ST manages 12.5 [inferred, from the measured
  renderer and the ST's split]. There's no co-processor edition
  (decision 8): the plain Master is the machine.
- **Memory was the harder limit, and the disc lifts it.** The whole game,
  as the ST has it, wants about 117K on the Master; about 96K is there.
  Loading by phase, as Elite does (the front end and the title, the
  docked screens, speech, the cockpit picture: decision 12), and keeping
  only the object fields the port uses (decision 13) leave about 86K in
  memory in flight, so about 10K to spend on speed [inferred].
- **Next**: an engine skeleton that settles the memory map, the disc
  reader and the frame (section 6), then the agents' optimisation pass
  within the budgets it sets, then the layers.

---

## 1. What the rest of the game costs in time

### The ST's frame

Hatari's CPU profiler over 33 seconds of flight and 8 near the energy
towers, the cycles at each address summed by area [measured 2026-10-18:
`tools/st_profile.py run tests/st/profile_flight.txt`, and `_towers`]:

| | Flight | The towers |
|---|---|---|
| Drawing (lists, transforms, faces, projection, clips, lines, the clear) | 68.0% | 76.9% |
| Ground dots | 8.7% | 6.4% |
| Waiting for the raster | 8.7% | 6.7% |
| Logic (flight, handlers, collisions, docking, the laser, random numbers) | 6.4% | 4.2% |
| Printing the score and messages | 3.7% | 2.6% |
| Panel (waveforms, gauges, scanner) | 3.6% | 2.5% |
| Other (sound, interrupts) | 0.8% | 0.8% |

Within those: the ground dots are 33 points a frame, each transformed and
divided; the score is printed again every frame; the gunsight's bitmap is
2%; the logic is mostly the loop over all 140 objects' handlers, most of
which do nothing, and the collisions over the near list.

### The Master's frame

*Revised 2026-10-18 after the engine skeleton (decision 14): the list
phase is in each step, not each frame.*

| Work | Cycles | |
|---|---|---|
| A step's list phase (camera and lists) | 58,000 mean in flight; 42,000 at the towers | [measured: `make spike`, after the object table's arrays] |
| A frame's objects and lines, logged for erasing | 167,000 mean in flight; 292,000 at the towers | [measured: `make spike`] |
| Erasing: the lines drawn two frames before | 16,000 in flight; 40,000 at the towers; 61,000 in the silo tunnel | [measured: `make spike`] |
| Ground dots: 33, each a transform and a reciprocal | 13,000-23,000 | [inferred] |
| Panel: scanner dots, gauges, changed digits, waveforms, the sight | about 8,000 | [inferred] |
| **A frame drawn** | **about 210,000: 5.3 fields** | |
| A step's logic (decision 4: one every 4 fields) | 15,000-30,000 | [inferred: the ST's 6% is exact 16- and 32-bit work, dearer on a 6502] |
| A sector read from disc, while it reads | 24% of the CPU for 20ms | [measured: CE2S, decision 12] |

A step (list phase and logic) is about 80,000 cycles, 12.5 a second:
about half the CPU, leaving room for **about 5 frames a second** at 210,000
each. If the pass halves the list phase and takes 30% off the drawing,
about **8** [inferred].

*After the optimisation pass (2026-10-18, `make spike`):* the list phase
is 34,600 cycles a step in flight, and a frame's objects, lines and erase
116,400. With about 20,000 of logic a step and 30,000 of dots and panel a
frame, that's **about 9 frames a second** in flight [inferred]. The ST: 12.5 in flight, 9 near the towers
[measured, docs/research/st.md]. Memory spent on speed (section 2) is the
pass's to use.

---

## 2. What the game needs in memory

Bytes on the Master, by part: the ST's figure where there is one
[measured: `tools/st_disasm.py --map` by area; docs/research/st.md], the
Master's from the port so far [measured: the build] or reckoned at 1.5-2
times the 68000's bytes for logic [inferred]. The last column says when
it must be in memory, and so whether it can come from disc.

| Part | The ST | On the Master | Needed |
|---|---|---|---|
| Renderer (lists, objects, clip, maths) | 4.5K + 4.9K drawing | 10.4K code + 3.7K tables (multiply, reciprocal) | always |
| Line drawer, vertex transforms (HAZEL) | | 4.0K | always |
| Disc reader (1770, NMI at &0D00) | | ~0.5K | always |
| Ground dots | 0.4K | ~0.6K | in flight |
| Logic: flight, handlers, missiles, collisions, docking, laser, bearing | 3.9K | ~6-7K | in play |
| Main loop, warnings, game over, keys and commands | 2.8K | ~4K | in play |
| Level set-up | 1.3K | ~2K | a level's start |
| Panel | 5.3K (with the mono paths) | ~3K + ~1K of bitmaps | in flight |
| Text: printers, messages | 2.2K + ~1.5K strings | ~1.5K + ~1.5K strings | in play |
| Docked: Interrogate, rearming, their descriptions | ~1K + ~3K strings | ~1.5K + ~3K strings | docked |
| Sound effects (the 8 the game starts, to the SN76489; built: about 0.9K) and the speech player | 2.0K | ~2.5K | in play |
| Front end: title, credits, keys, high scores, the end screen | ~2K + strings | ~4K + ~2K | outside play |
| Shapes | 34K | 16.1K | in play |
| Sine table | 12K | 10.5K now; ~3K as a quarter wave and corrections | in play |
| Arctan tables (the logic's bearing) | 2K | 2K | in play |
| Per-type tables | 0.7K | 0.7K | in play |
| Level layouts | 3.1K | 3.1K | a level's start |
| Object table, 142 records | 9.1K | ~4.5K with only the fields the port uses (decision 13) | in play |
| Vertex arrays, marks, lists | | 2.4K | in play |
| Erase lists, both screens (lines, dots, scanner) | | ~3K | in play |
| The cockpit picture, packed | 32K | ~5K | when it's drawn: play's start, after docking |
| The title picture | 32K | ~5K | the title |
| Speech: four clips | 27K | 13.5K at 6kHz (9K at 4kHz); the docked one 3.6K of it | the clip's moment |
| Title song | 179K | ~3K as the AY tune, or the ST's sample streamed | the title |

And what the Master has, once the game owns it (docs/research/beeb.md,
section 2):

| Where | Bytes | |
|---|---|---|
| Main RAM &0E00-&417F, below the screen | 13,184 | |
| The OS's pages &0400-&0DFF | 2,560 | &0D00-&0DFF for the disc reader's NMI routine |
| Shadow RAM's &3000-&417F, beside the shadow screen | 4,480 | only while ACCCON's X is set: from HAZEL |
| HAZEL &C000-&DFFF | 8,192 | free once the game drives the disc itself |
| ANDY &8000-&8FFF | 4,096 | over the paged bank's first 4K |
| Sideways RAM, banks 4-7 | 65,536 | one bank at a time |
| **All told** | **about 96K** | |

**In memory in flight**, then: everything the table marks always, in
play or in flight, with the sine table compacted and the object table cut
down (decision 13), comes to about 71K; the level set-up and all 34
levels' layouts, 5K, stay too, as they're small and a level changes in
flight. Flight's three speech clips, 10K at 6kHz, make about 86K. The
docked screens and their clip, the cockpit picture, the front end and
the title's picture and song come from disc when they're wanted (section
5) [inferred]. That leaves about 10K, which the optimisation pass can
spend on speed: more of the inner loops unrolled, products kept by
coordinate value, the full sine table rather than its quarter.

**What must be visible at once** constrains where things go more than the
totals do, since only one bank is paged at a time:

- the list phase: the objects, the camera, the rotation code, the
  multiply tables;
- the draw phase: the shapes, the drawn objects' positions and angles,
  the transforms, the line drawer, the multiply and reciprocal tables;
- the logic: its code, the objects, the sine and arctan tables, the
  per-type tables;
- the speech interrupt: the samples (it can page their bank itself, at a
  few cycles a sample);
- the disc reader's NMI: the page it stores into, which can be anywhere
  but a bank other than the one paged.

---

## 3. The memory map

The principle: everything that touches the objects in one place, the
**world**; the drawing in another, working from a **draw list** of the
few objects drawn, which the list phase fills (their positions, the sines
of their angles), so the draw phase needs only the shapes' bank. What
comes from disc lands in a **loading area** that the phase it serves
owns.

| Where | Holds |
|---|---|
| Zero page | fixed state (the inputs, the multiply pointers) and baron's pool |
| OS pages &0400-&0CFF | vertex arrays and marks, the lists, the draw list |
| &0D00-&0DFF | the disc reader's NMI routine |
| Main RAM &0E00-&417F | the draw phase's code, the main loop, the interrupts and the disc reader, the object table; and the start, which follows the resident code in SG and may lie over the lists and objects, as it runs once before they're used (`src/start.6502`) |
| Shadow RAM &3000-&417F | the erase lists, read and written only with X set: by HAZEL's code, and the objects' boxes by bank 7's (`src/box.6502`) |
| HAZEL | the multiply and reciprocal tables, the line drawer, the screen's clear, the vertex transforms |
| ANDY | *as built:* the object fields only the logic reads, and the logic's variables (`src/vars.6502`): paged in with the logic's banks, over their first 4K |
| Bank 4 | the shapes, and past them the draw phase's code that runs only with them paged (`src/shapecode.6502`: far_place's centre and quarters, the box's box_out and box_x) |
| Bank 5 | the world: below &9000 the list phase, run with ANDY out (its end, `world_list_end`, just short of the sine table's 1K alignment); from &9000 the sine table and the logic that reads it (`world_render`'s, the flight, the handlers), with what only that logic takes (`fmul15`, the handlers' `h_random32`, `animate_shapes`'s lists); and at its end the drawing's products that build_matrix and the ground matrix take (`kmul`, `matrix_heading`) and `ground_camera`, whose callers have the bank paged |
| Bank 6 | *as built:* the rest of the logic from `world_list_end` (the keys, the laser, collisions, the frame's end, the level change), the logic's drawing records (`src/view.6502`: the bolt and the shots) and the panel (`src/panel.6502`), its data in the gap from &9000 to `world_list_end`. Below &9000 it holds no code (baron#29, our issue #1) and is free for data, readable only with ANDY out |
| Bank 7 | *as built in flight:* the missile view's window picture and the draw phase's view code (`src/view_under.6502`, `src/mview.6502`), the objects' boxes (`src/box.6502`) and the cockpit's screens' copy and the window's clear, which set ACCCON's X (`src/screen.6502`), the code past `world_list_end`; below &9000 no code, free for data read with ANDY out. *Planned:* flight's speech, which needs a call (the four clips are 13.4K at the ST's rate, and the room with no code in it in banks 6 and 7 adds to about 11.5K); the docked screens and their clip when docked; the front end and the title outside play |

The banks' first 4K hold no code until baron#29 is fixed: the rotations'
annotated jumps fill bank 5 there, and a jump of another bank's at one of
their addresses would take on its targets. Data is fine there, for
whatever reads it with ANDY out, the speech player's interrupt above
all. Every annotated jump outside the rotations' chain sits in main RAM
(`handler_dispatch`, `set_up_dispatch`).

Each region gets a budget, `ASSERT`ed in the build (section 6), so a part
that grows says so at once.

---

## 4. The frame (proposed)

- **Interrupts**: the game owns the machine. The vertical sync counts
  fields, flips the screens when a frame is ready (ACCCON's D), and sets
  the view's palette; a VIA timer splits the palette at the view's bottom
  edge for the cockpit (decision 3); another plays speech while a clip is
  speaking (decision 5); the disc reader's NMI takes each byte while a
  sector is read (decision 12). An NMI can delay a palette split by a few
  microseconds: CE2 found the glitch very hard to spot and accepted it
  (its decision 50).
- **The game steps on the field count**, one step every 4 fields
  (decision 4's 12.5 a second). A step is the list phase then the logic,
  since the logic reads the lists (decision 14). The main loop runs every
  step that's due, and the last one draws a frame between its lists and
  its logic, the ST's own order. A heavy scene drops frames; the game's
  pace holds. Built: `src/engine.6502`.
- **A frame**: the draw phase draws the draw list's objects into the
  hidden screen, after erasing what was drawn there two frames before,
  and logs what it draws for the next erase, in shadow RAM: each line,
  or for an object cheaper erased so, the box of bytes its lines lie in
  (decision 20, `src/box.6502`); the panel's changes are drawn into the
  hidden screen too, each screen remembering what it shows.

---

## 5. The disc (decision 12)

Chuckie Egg 2's streaming edition built and measured a 1770 reader on a
Master that the game can take as it is [measured,
`../chuckie-egg-2-beeb/docs/streaming.md`]: an NMI routine at &0D00
stores each byte (35 of the 128 cycles between bytes), a sector takes
20ms warm and a whole track one revolution (about 12.5K a second),
stepping is 6ms a track, and from cold the motor's spin-up costs 1.3s.
The drive stops by itself when idle, which Matt preferred to having it
run (CE2's decision 35).

How each part would use it, as Elite loads its docked and flying code,
each load into bank 7 over what the phase before needed. A load's time
is about 0.08s a kilobyte, plus 1.3s if the drive has stopped
[inferred, from CE2S's figures]:

| Load | When | What covers it in the ST's game | Bytes |
|---|---|---|---|
| The cockpit picture and flight's speech, over the front end | the game's start | nothing in the ST's: the game waits, about 1.2s, with the drive still turning if the title song was streaming | ~15K |
| The docked screens and the docked clip, over flight's speech | entering a silo | the tunnel's flight in [measured: 89 frames at 3.7 VBLs, about 6.6s on the ST], then the wait for SPACE | ~8K |
| Flight's speech again | launching from a silo | "LAUNCHING FROM SILO"; speech isn't wanted at once | ~10K |
| The front end and the title picture | game over | the GAME OVER words turning | ~11K |
| The title song, sampled | while the title plays | streamed, a track at a time | ~55K on the disc (18.2s at 6kHz, 4 bits a sample) |

**Speech** (Matt: loaded, or streamed). Loaded at the game's start, the
three clips flight uses (missile launched, shields low, energy low) stay
in bank 7 through flight, and the docked one (rearmed) comes with the
docked screens. Streaming each clip as it's spoken would
free their 10K too, but a clip lasts about a second and a cold drive
takes 1.3s to spin up, so a clip would start late unless the drive kept
spinning through play, which Matt found annoying in CE2. Worth measuring
once the reader is in, since only the first part of each clip would need
to be in memory.

---

## 6. The order of work

1. **An engine skeleton**, the renderer kept passing `make spike`. Built
   on 2026-10-18:
   - the memory map of section 3 (`src/memory.6502`), each region's guard
     its budget, and `make memory` to show them;
   - the renderer split into the list phase (world bank,
     `src/world.6502`) and the draw phase;
   - the sine table compacted, and the object table made an array a
     field (decision 13), its fields joining as the logic is transcribed;
   - the interrupts, the field count, the fixed step, the flip and the
     erase lists (`src/engine.6502`, decision 14), with the disc showing
     it running, and `make fps` to measure it.

   CE2S's 1770 reader comes with the first layer that loads something
   (speech or the front end); its NMI page, &0D00, is kept free.
2. **The optimisation pass**: a team of agents, each in its own worktree
   and owning one area (the lists and rotation; each object's set-up; the
   vertices and projection; faces, edges and the window clip; drawing and
   erasing lines), each gated by `make spike` (logic exact, lines within
   a pixel, cycles) and its region's byte budget, in rounds until a round
   finds little.
3. **The layers**, as the brief has them: the screen (the cockpit, the
   palette split), the data, flight (the player, ground dots, scanner,
   gauges), the world, silos, sound, the front end, the loader.

## 7. Calls made

Matt, 2026-10-18: no co-processor edition (decision 8); the front end
loaded from disc, and speech loaded or streamed (decision 12); the
object table cut to the fields the port uses (decision 13); speech at
6kHz if it fits, 4kHz if not (decision 5). The title song is still to be
chosen by ear (decision 5), and streaming makes the ST's own sample one
of the options at no cost in memory.
