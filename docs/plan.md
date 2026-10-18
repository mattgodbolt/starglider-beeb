# After the spike: a plan for the rest of the game

*Written on 2026-10-18, after the speed spike, as the step back before
the renderer's optimisation pass. The tags are the brief's:
**[measured]** (run or read, the tool named), **[source]**, **[inferred]**
(reasoning or arithmetic: check before relying on it).*

## In short

- **The ST's own frame**, profiled in Hatari: in flight 68% of its time
  goes on drawing, 9% on the ground dots, 9% waiting for the raster, 6% on
  the game's logic, 4% on printing the score and messages, 4% on the
  panel [measured: `tools/st_profile.py`].
- **The Master's frame** is about 6.7 fields drawn plus a logic step every
  4 fields, so about 6.5 frames a second at the ST's game speed
  (decision 4); after the optimisation pass, about 9. The ST manages 12.5
  [inferred, from the measured renderer and the ST's split].
- **Memory binds harder than time.** The whole game, as the ST has it,
  wants about 117K on the Master; about 96K is there. It just fits if the
  sine table is compacted, the object table keeps only what the port
  uses, and the front end is loaded from disc when it's wanted, with
  nothing to spare; with speech at 4kHz too, about 4.5K [inferred].
- **The co-processor is the way to the ST's speed**, and it would end the
  memory squeeze too: the logic and the maths, about three quarters of the
  work, would run at 4MHz in their own 64K while the Master draws. So the
  engine should be built around a display list now (decision 8's seam),
  with the single-processor game first.
- **Next**: an engine skeleton that settles the memory map and the frame
  (section 6), then the agent optimisation pass within the budgets it
  sets, then the layers.

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

| Work | Cycles | |
|---|---|---|
| The renderer (lists, objects, lines) | 226,000 mean in flight; 331,000 at the towers | [measured: `make spike`] |
| Ground dots: 33, each a transform and a reciprocal | 13,000-23,000 | [inferred] |
| Panel: scanner dots, gauges, changed digits, waveforms, the sight | about 8,000 | [inferred] |
| Erasing: the lines and dots drawn two frames before | about 14,000 | [inferred: a line erased costs what it cost to draw] |
| **A frame drawn** | **about 265,000: 6.7 fields** | |
| A logic step (decision 4: one every 4 fields) | 15,000-30,000 | [inferred: the ST's 6% is exact 16- and 32-bit work, dearer on a 6502] |

At 6.7 fields a frame, 1.7 logic steps fall in each, so a frame is about
7.6 fields: **6.5 frames a second**. If the optimisation pass takes 30%
off the renderer, 5.7 fields: **about 9** [inferred]. The ST: 12.5 in
flight, 9 near the towers [measured, docs/research/st.md].

---

## 2. What the game needs in memory

Bytes on the Master, by part: the ST's figure where there is one
[measured: `tools/st_disasm.py --map` by area; docs/research/st.md], the
Master's from the port so far [measured: the build] or reckoned at 1.5-2
times the 68000's bytes for logic [inferred].

| Part | The ST | On the Master | When it's needed |
|---|---|---|---|
| Renderer (lists, objects, clip, maths) | 4.5K + 4.9K drawing | 10.4K code + 3.7K tables (multiply, reciprocal) | always |
| Line drawer, vertex transforms (HAZEL) | | 4.0K | always |
| Ground dots | 0.4K | ~0.6K | in play |
| Logic: flight, handlers, missiles, collisions, docking, laser, bearing | 3.9K | ~6-7K | in play |
| Main loop, warnings, game over, keys and commands | 2.8K | ~4K | in play |
| Level set-up | 1.3K | ~2K | at a level's start |
| Panel | 5.3K (with the mono paths) | ~3K + ~1K of bitmaps | in play |
| Text: printers, messages, the Interrogate descriptions | 2.2K + 4.6K strings | ~1.5K + ~3K strings | in play |
| Sound effects (24, to the SN76489) and the speech player | 2.0K | ~2.5K | in play |
| Front end: title, credits, keys, high scores, the end screen | ~2K + strings | ~4K + ~2K | outside play |
| Shapes | 34K | 16.1K | always |
| Sine table | 12K | 10.5K now; ~3K as a quarter wave and corrections | always |
| Arctan tables (the logic's bearing) | 2K | 2K | in play |
| Per-type tables, level layouts | 0.7K + 3.1K | 3.8K | in play |
| Object table, 142 records | 9.1K | 9.1K as the ST lays it out; ~4.5K with only the fields the port uses | always |
| Vertex arrays, marks, lists | | 2.4K | always |
| Erase lists, both screens (lines, dots, scanner) | | ~3K | always |
| The cockpit picture, packed | 32K | ~5K | in play (redrawn after docking) |
| The title picture | 32K | from disc | the title |
| Speech: four clips | 27K | 13.5K at 6kHz (9K at 4kHz) | in play |
| Title song | 179K | ~3K (the AY tune) or streamed | the title |
| **All told** | | **about 117K** | |

And what the Master has, once the game owns it (docs/research/beeb.md,
section 2):

| Where | Bytes | |
|---|---|---|
| Main RAM &0E00-&417F, below the screen | 13,184 | |
| The OS's pages &0400-&0DFF | 2,560 | |
| Shadow RAM's &3000-&417F, beside the shadow screen | 4,480 | only while ACCCON's X is set: from HAZEL |
| HAZEL &C000-&DFFF | 8,192 | |
| ANDY &8000-&8FFF | 4,096 | over the paged bank's first 4K |
| Sideways RAM, banks 4-7 | 65,536 | one bank at a time |
| **All told** | **about 96K** | |

So it doesn't fit as it stands: about 21K over [inferred]. What closes
the gap:

| | Saves | Costs |
|---|---|---|
| The sine table as a quarter wave plus the ST's corrections | ~7.5K | a few cycles a lookup, a handful a frame |
| The object table with only the fields the port uses | ~4.6K | the checks translate between layouts |
| The front end loaded from disc when it's wanted | ~9K | a disc load at the title and at the game's start |
| Speech at 4kHz | 4.5K | muffled speech (decision 5's fallback) |

With the first three, about 95.5K of 95.75K: it fits, with nothing to
spare. With speech at 4kHz too, about 4.5K to spare.

**What must be visible at once** constrains where things go more than the
totals do, since only one bank is paged at a time:

- the list phase: the objects, the camera, the rotation code, the
  multiply tables;
- the draw phase: the shapes, the drawn objects' positions and angles,
  the transforms, the line drawer, the multiply and reciprocal tables;
- the logic: its code, the objects, the sine and arctan tables, the
  per-type tables;
- the speech interrupt: the samples (it can page their bank itself, at a
  few cycles a sample).

---

## 3. A memory map (proposed)

The principle: everything that touches the objects in one place, the
**world**; the drawing in another, working from a **draw list** of the
few objects drawn, which the list phase fills (their positions, the sines
of their angles), so the draw phase needs only the shapes' bank.

| Where | Holds |
|---|---|
| Zero page | fixed state (the inputs, the multiply pointers) and baron's pool |
| OS pages &0400-&0DFF | vertex arrays and marks, the lists, the draw list |
| Main RAM &0E00-&417F | the draw phase's code, the main loop and the interrupts, the display list; the object table if it's compacted |
| Shadow RAM &3000-&417F | the erase lists, read and written only by HAZEL's code with X set |
| HAZEL | the multiply and reciprocal tables, the line drawer, the screen's clear, the vertex transforms |
| ANDY | the logic's tables (arctan, per-type) and the messages: paged in with the world bank, it hides that bank's first 4K, so that 4K holds what the logic doesn't read |
| Bank 4 | the shapes |
| Bank 5 | the world: the logic's code, the list phase's rotation, the sine table |
| Bank 6 | the rest of the game's code (panel, text, sound effects, level set-up, Interrogate), the level layouts, the cockpit picture |
| Bank 7 | speech; the front end's overlay takes it outside play, and speech is loaded again at the game's start |

Each region gets a budget, `ASSERT`ed in the build (section 6), so a part
that grows says so at once.

---

## 4. The frame (proposed)

- **Interrupts**: the game owns the machine. The vertical sync counts
  fields, flips the screens when a frame is ready (ACCCON's D), and sets
  the view's palette; a VIA timer splits the palette at the view's bottom
  edge for the cockpit (decision 3); another plays speech while a clip is
  speaking (decision 5).
- **The game steps on the field count**, one step every 4 fields
  (decision 4's 12.5 a second; to be settled by measurement against the
  ST's mean). The main loop runs every step that's due, then draws a
  frame of the latest state. A heavy scene drops frames; the game's pace
  holds.
- **A frame**: the list phase (in the world bank) fills the draw list;
  the draw phase turns it into a **display list** of lines and dots; the
  display list is drawn into the hidden screen, after erasing what was
  drawn there two frames before; the panel's changes are drawn into the
  hidden screen too, each screen remembering what it shows.
- **The display list is decision 8's seam.** With a co-processor, the
  co-processor runs the steps, the list phase and the draw phase and
  sends the display list across the Tube (a few hundred bytes a frame);
  the Master erases, draws, keeps the panel and plays the sound.

---

## 5. The co-processor

The Master's internal 6502 second processor (a 65C102 at 4MHz) has its
own 64K. Split at the display list, about three quarters of the work in
section 1 moves to it [inferred]:

| | Single processor | With the co-processor |
|---|---|---|
| A frame | ~6.7 fields (5 after the pass) | ~3 fields on the co-processor, ~1.2 on the Master, in parallel [inferred] |
| Frames a second at the ST's pace | ~6.5 (~9) | 12.5, the ST's step [inferred] |
| Memory | all but full | the logic and the maths in the co-processor's 64K: the Master keeps the screens, the line drawer, the panel and the sound |

Most Masters don't have one, so the plain Master stays the edition the
game is made for; the co-processor's is built once the game runs, from
the same source.

---

## 6. The order of work

1. **An engine skeleton**, the renderer kept passing `make spike`:
   - the memory map of section 3, with each region's budget `ASSERT`ed;
   - the renderer split into the list phase (world bank) and the draw
     phase (draw list in, display list out);
   - the sine table compacted, and the object table's layout settled;
   - the interrupts, the field count, the fixed step and the flip, with
     the disc showing it running.
2. **The optimisation pass**: a team of agents, each in its own worktree
   and owning one area (the lists and rotation; each object's set-up; the
   vertices and projection; faces, edges and the window clip; drawing and
   erasing lines), each gated by `make spike` (logic exact, lines within
   a pixel, cycles) and its region's byte budget, in rounds until a round
   finds little.
3. **The layers**, as the brief has them: the screen (the cockpit, the
   palette split), the data, flight (the player, ground dots, scanner,
   gauges), the world, silos, sound, the front end, the loader.

## 7. Calls to make

| | Options | Recommendation |
|---|---|---|
| **The object table's layout** | (a) the ST's 64-byte records, as now: 9.1K, byte-for-byte checks as they are; (b) only the fields the port uses: ~4.5K, the checks translating between the layouts | (b): memory is what's short, and the translation is the checker's job, once |
| **The front end** | (a) resident; (b) loaded from disc into the speech bank at the title, speech loaded again at the game's start | (b): ~9K that play never needs |
| **Speech** (decision 5) | 6kHz (13.5K), 4kHz (9K) | keep 6kHz in the plan, with 4kHz as the margin if the map doesn't close |
| **The co-processor** (decision 8) | (a) later, as decision 8 has it; (b) the display list now, the edition when the game runs | (b): the seam costs about a thousand cycles a frame, and the edition is the way to the ST's speed |
