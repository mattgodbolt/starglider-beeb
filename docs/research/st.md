# Starglider on the Atari ST

Argonaut Software's original, by Jez San: `AUTO/STAR.PRG` on
`original/st/Starglider (1987)(Rainbird).st` (TOSEC's image), run from the
protected master `original/st/Starglider (1987)(Rainbird).stx`. Its strings say
"StarGlider, (c)1986 Argonaut Software Ltd., by Jez San. Published by BT
Rainbird, London, UK. Completed, Sept 1986."

Addresses are **offsets into STAR.PRG's text segment** (the program loaded
at 0), written `&1234`. Variables written `$123(a6)` are offsets from the
game's variable block at the fixed address &5BF00. Hatari's EmuTOS loads the
text segment at &109BE, so a Hatari PC minus &109BE is an offset here.

Every claim is tagged: **[measured]** (a tool was run or the bytes read; the
tool or address is named), **[source]** (with a link) or **[inferred]** (a
reading, with what would check it).

The tools (all in `tools/`, all run with `.venv/bin/python -I`):

| Tool | What it does |
|---|---|
| `st_prg.py` | loads a GEMDOS program and applies its relocation table; `--strings` |
| `st_disasm.py` | recursive-descent 68000 disassembly with Capstone, labels from `st_star.ctl` |
| `st_star.ctl` | the control file: roots, jump tables, labels and comments found so far |
| `st_shapes.py` | the shape table, every shape as PNG, animation strips, a contact sheet, JSON |
| `st_tra.py` | `.TRA` pictures (and raw 32000-byte screens) to PNG |
| `st_samples.py` | the embedded samples: table, and WAV export |
| `st_hatari.py` | drives a headless Hatari through its command FIFO (keys, mouse, screenshots, debugger) |
| `st_workload.py` | counts lines, pixels, vertices, objects and dots per rendered frame in Hatari, and reports their distributions |
| `st_scenes.py` | captures scenes in Hatari: each frame's variables, objects and shape table, and every line drawn, by object (scripts in `tests/st/`) |
| `st_render.py` | a model of the renderer, exact to the 68000's arithmetic, checked against the captured lines |

## Summary for the port

| Figure | Value | |
|---|---|---|
| STAR.PRG | 310,054 bytes: header 28, text 308,952 (&4B6D8), data 0, BSS 0, relocation table 1,073 bytes (758 fixups) | [measured] `st_prg.py` |
| Code area | &00000-&0ABF6, 44,022 bytes, including its strings, small tables and variables; 30,166 bytes of instructions reached from the known roots | [measured] `st_disasm.py --map` |
| Shape data | 29 table entries (28 shapes) at &0AF4E, data &0B11E-&13566 (33,864 bytes, animation frames included); 524 vertices and 802 edges in the base frames | [measured] `st_shapes.py` |
| Animated shapes | 7 frame lists: Walker 16 frames, Starglider drone 9, Stomper 29, energy beam 20, silo 11, Pyramid Launcher 35, StarGlider One 37 | [measured] `st_shapes.py`, &043EE |
| Trig tables | sine 6,145 words (&13D6C-&16D6E, 2.14 fixed point, 4096 steps a turn; cosine is the same table 1024 entries on); two arctan tables of 513 words (&13568, &1396A) | [measured] |
| World | a 65,536-unit torus (16-bit x and z wrap); 100 x 100 sectors of &290 (656) units; four object layouts of 82, 89, 97 and 114 objects | [measured] &0A6AE, &17C88 |
| Samples | four speech clips, 27,136 bytes played (0.94-1.21 s each at 6144 Hz) and the title song, 179,200 bytes (18.2 s at 9830 Hz); 8-bit, through the YM2149's three volume registers from MFP Timer A | [measured] `st_samples.py`, &01AF8 |
| Screen | ST low res, 320 x 200, 16 colours; the 3D view is 288 x 119 at (16, 10); double-buffered at &70000 and &78000 | [measured] &08CA0, &0A56E, screenshots |
| Line colour | one colour per object (the shape's face colour), ORed into the bitplanes | [measured] &04B1C, &09128 |
| Hidden lines | back faces of each object are culled; objects never hide one another | [measured] &04BE8, screenshots |
| Clear | the view window only: 119 lines x 144 bytes = 17,136 bytes a frame, `movem.l` | [measured] &099D0 |
| Frame rate | no fixed rate: a frame takes 2-6 VBLs (25-8.3 fps). A 704-frame flight sample averaged 3.69 VBLs (13.5 fps); near the energy towers 5-6 (9 fps); docked 2 (25 fps) | [measured] Hatari, breakpoint on &08EC2 |
| Work per frame | flight: median 29 lines of 3-4 pixels (109 pixels), 28 vertices drawn plus 105 transformed for the back-face test, 4 objects; the energy towers close up: 90 lines, 525 pixels, 51 + 228 vertices, 7 objects, 6 VBLs; the silo tunnel: 49 lines, 1,943 pixels, 4 VBLs | [measured] `st_workload.py` |
| Projection | x' = 128x/z + 143, y' = 128y/z + 68 (colour); near plane z = 2; 2D clip to the window | [measured] &04D66, &0A374, &0A170 |
| Memory | uses fixed RAM: variables at &5BF00, screens &60000-&7FFFF, game variables in low RAM (&A0, &1E4, &29C, &2CF, &94C, &1218...) | [measured] disassembly |

## The images

`docs/images/st/` holds (all made by the tools above):

- `title_tra.png`, `result_tra.png`: TITLE.TRA and RESULT.TRA. RESULT.TRA
  is the cockpit.
- `shape01.png` ... `shape28.png`, `shapeNN_frames.png` for the animated
  ones, and `shapes_sheet.png`: every shape in the flight palette, the edges
  of front faces in the shape's colour and the rest dim grey.
- `hatari_*.png`: emulator screenshots, 320 x 200: the title, the credits,
  flight, a close-up of an energy tower (hidden lines removed), an enemy
  laser hit, the silo interior, the silo's menu and the Interrogate screen.

## The layout of STAR.PRG

STAR.PRG is a plain GEMDOS program. The relocation table touches only
&00112-&17D3C, so everything above (the samples) is position-free data
[measured] `st_prg.py`. The program keeps SHAPE.DAT, star.snd and
clare1-4.snd inside itself; their names survive at &0A62C-&0A6AE, but
nothing references them. The only files it opens are title.tra and
result.tra [measured]: Hatari's GEMDOS trace (`--trace gemdos`) shows
exactly two `Fopen`s, from &04A28.

| Range | Bytes | What | |
|---|---|---|---|
| &00000-&00098 | 152 | `bra` to &01E5A, the copyright strings, "YOU NOW HAVE MANUAL CONTROL!" | [measured] |
| &00098-&0ABF6 | 43,870 | code, with inline strings (messages, credits, object descriptions, high scores), small tables and variables (e.g. the key-state array &017C2, the mouse accumulators &01842-&0184C, the score &0150C) | [measured] |
| &0ABF6-&0AC76 | 128 | chunky-to-planar table for the .TRA unpacker | [measured] &0AACA |
| &0AC76-&0AF4E | 728 | per-type tables (below): type to shape, collision boxes, damage, scores | [measured] |
| &0AF4E-&0B11E | 464 | the shape table, 29 x 16 bytes | [measured] &04B1C |
| &0B11E-&13566 | 33,864 | shape data (vertices, edges, faces, animation frames and their lists) | [measured] |
| &13568-&13D6C | 2,052 | two arctan tables, 513 words each | [measured] &08390 |
| &13D6C-&16D6E | 12,290 | sine table, 6,145 words | [measured] |
| &16D6E-&16D88 | 26 | unidentified | |
| &16D88-&17C88 | 3,840 | fonts and small bitmaps: the colour font at &16D88 (8 x 8), the mono font at &170E8, others | [measured] &01264, &01134 |
| &17C88-&17D40 | 184 | 46 pointers to the level layouts | [measured] &0A728 |
| &17D40-&18948 | 3,080 | four layouts, 8 bytes an object | [measured] |
| &18948-&18DB0 | 1,128 | zeros: the stack (`lea &18DB0,a7` at &01E60) | [measured] |
| &18DB4-&4B3B4 | 206,336 | the samples, end to end: clare1-4 then star | [measured] `st_samples.py` |
| &4B3B4-&4B6D8 | 804 | zeros | [measured] |

The copy protection: the TOSEC image boots but the program halts at
`stop #$2700` (&034FC) [measured]: Hatari, PC &13EBA = &109BE + &034FC.
The code before it reads the disc itself: it selects the drive through YM
register 14 (&033FE) and polls the FDC's interrupt on MFP GPIP bit 5
(&03438, &034CC, &0354C) [measured]. The EMT crack's 47 changed bytes are a
`bra.w` over the check at &033FE (4 bytes), one byte at &034E0, the halt at
&034FC (4 bytes) and 38 bytes of the credits at &03BD2 [measured]: `cmp` of
the two programs. The `.stx` master passes the check in Hatari [measured].

The crack's extra files (FIL1-8, PRES, EDIT1.PIC, STRIP.PRG) are Pirasoft's
"Strip Breakout" (1987), not Starglider [measured]: rendered with `st_tra.py
--raw` (they're raw ST screens; the title text is "Strip Break out, de Renan
Jegouzo, Pirasoft 1987"). They're not in `docs/images/st/`.

### Fixed addresses

The program is relocatable, but much of what it uses is not [measured]:
the operands below aren't in the relocation table.

- **The variable block** is at &5BF00 (`lea &5BF00,a6` at &01E5A); every
  `$nnn(a6)` below is there. On EmuTOS this overlaps the last 406 bytes of
  the program (zeros). [measured]
- **Screens**: &70000 and &78000 (32,000 bytes each, swapped every frame);
  TITLE.TRA is unpacked to &68000 (palette at +2, bitmap at +&22) and
  RESULT.TRA to &60000, and the swap routine swaps &60000/&68000 along with
  the screens in `8(a6)`/`12(a6)` [measured] &032EC, &0A56E. What those two
  slots do in flight is open.
- **Low RAM used as variables**: &1E4 (the VBL count), &29C (a countdown the
  VBL decrements), &A0/&A4 (sample start and length; they're trap vectors
  TOS doesn't use), &2CF/&2D0 (Timer A control and data), &94C (ten object
  pointers), &1218 and &1258 (two 64-byte objects: the silo tunnel and the
  missile in it) [measured] &000A2, &01A50, &0A6DA, &085E6. Several of
  these look like a6-relative addresses written absolute (the object array
  is at &129A(a6); the two silo objects sit just below &129A) [inferred:
  it makes no difference to a port, which needs only the layout].

## The engine

### Start-up (&01E5A)

1. `Super`, then Line-A init and hide-mouse (&0A534), ESC f [measured].
2. `init_resolution` (&08CA0): reads the Shifter's mode; on a colour
   monitor it forces low res and sets the colour flag `$2BC(a6)`. It sets
   the view window, the projection centre and six function pointers (line,
   dot, two text printers, view clear, bitmap blit) for colour or mono
   [measured] &0493A, &08CB8-&08E48.
3. The start-up palette (&08E82) [measured] &08E56.
4. VBL handler &000A2 into &70, keyboard/MIDI ACIA handler &00C32 into
   &118, then the IKBD is set up: &0B 1 1 (mouse threshold 1, 1) and 7 4
   (mouse buttons as keys) [measured] &00A9E, [source] the IKBD protocol
   (link under the laser, below).
5. title.tra and result.tra are loaded at &70000 and unpacked; the samples
   are flipped to unsigned [measured] &032EC, Hatari RAM dump.
6. The title loop plays the song and waits up to &44C VBLs for a key: K
   redefines the keys (&022BA), G (cheat mode only) opens a model viewer,
   any other starts the game; with no key it alternates the title with the
   credits [measured] &01EAC-&01EFA.

### Interrupts

- **VBL** (&000A2): adds 1 to &1E4 and decrements &29C if non-zero.
  Nothing else [measured].
- **ACIA** (&00C32): key press/release into the key-state array &017C2
  (one byte per scancode) and the last key into &01852; mouse packets: dx
  added to &01842 (turn), dy to &01844 (climb), or to &01848 (speed) while
  the right button is down; the buttons into &0184A/&0184C [measured].
- **Timer A**: the sample player (&01AF8) or the sound-effect routines
  [measured] &01A58, &00180.

### The frame (&01F10)

| Order | Routine | What |
|---|---|---|
| 1 | `world_render` &04FE8 | clear the view (&099D0 via `$40(a6)`), the docking/refuelling messages, the score, the camera from the player's angles, the ground dots (&047AA), the near and draw lists (&0561C, &057B8), every object in the draw list (&04B1C, or &04DAC if exploding), the panel (&05872, the waveforms), the player's laser (&0866C), "LAUNCHING FROM SILO" |
| 2 | `read_keys` &0270E | command keys, and the flight keys from the key-state array |
| 3 | `player_flight` &077B4 | move the player along its heading; turn the mouse accumulators into bank and climb |
| 4 | `object_handlers` &07A54 | each object's handler (table &08252), and the explosions' 32-frame countdown |
| 5 | `animate_shapes` &043EE | step the seven frame lists |
| 6 | `collisions` &08416 | ramming, docking, refuelling, mines |
| 7 | `level_message` &0260C | "LEVEL n" for 50 frames after a level change |
| 8 | `frame_end` &08EC2 | count the frame (`$1E2(a6)`), wait for the raster, colour 0 from `$242(a6)`, swap |

Then the warnings (speech when shields or energy fall below &2EE0) and the
game-over tests (&01F38-&020B6) [measured].

### Frame pacing and double buffering

`frame_end` (&08EC2) doesn't wait for a VBL. It waits until the Shifter's
video counter is past line 192 (`$FF8207 & $7F >= $78`, &0A55C), writes
colour 0, and swaps (&0A56E): the drawn screen's base goes to `$FF8201/3`
(it takes effect at the next VBL) and `0(a6)` (the draw buffer) and `4(a6)`
trade places [measured]. So the game runs flat out, and a frame takes a
whole number of VBLs.

Measured in Hatari (cycle-exact 68000, its default), with a breakpoint at
`frame_end` printing the VBL counter on every frame [measured]
`st_hatari.py`:

| Situation | Frames | VBLs a frame |
|---|---|---|
| Flight from the start, flying forward, a turn | 704 | 2: 46, 3: 316, 4: 188, 5: 118, 6: 36; mean 3.69 (13.5 fps) |
| The energy-tower group in view, 3,000 units off | 58 | 5 and 6 alternating (9.1 fps) |
| An energy tower close up, a tank and a fighter in view | 27 | 6, then 5 (8.3-10 fps) |
| Docked in a silo, then the Interrogate screen | 541 | 2 almost throughout (25 fps) |
| The game's own counters over 504 VBLs at the start | 93 | 5.4 (9.2 fps) |

The floor is 2 VBLs even with nothing to draw [measured]: docked.

### Work per frame

Counted per rendered frame in Hatari with `st_workload.py` [measured].
Breakpoints on the routines below add to Hatari's virtual registers, and
one on `frame_end` (&08EC2) prints and zeroes them with the VBL count.
Breakpoints don't change the emulated timing: the tower cases took 5.5 and
6.0 VBLs a frame, as they did unwatched.

- **Lines drawn**: calls reaching the line drawer's dispatch (&09172 for
  y-major, &091B8 for x-major), after both clips. The lasers go through
  the same drawer (&05606), so they're included.
- **Pixels**: max(|dx|, |dy|) + 1 for each line, read from d3 or d2 at
  the dispatch: the drawer's loop count.
- **Vertices transformed**: calls of `transform_vertex` (&03FFE), the
  vertices of visible faces. **Normal vertices**: calls of &04320, three
  for each face given the back-face test (faces marked always-visible
  skip it).
- **Objects drawn**: calls of `draw_shape` (&04B1C) and
  `draw_shape_exploding` (&04DAC); always equal to the draw-list length
  `$23E(a6)`, which was read too.
- **Dots**: calls of `dot_colour` (&0976E), the ground dots. The
  scanner's dots are plotted by &05E0C directly and aren't counted.

Each cell is mean / median / 90th percentile / max:

| Situation | Frames | VBLs a frame | Lines drawn | Pixels | Pixels a line | Vertices transformed | Normal vertices | Objects drawn | Dots |
|---|---|---|---|---|---|---|---|---|---|
| Flight from the start (forward, a turn) | 711 | 4 / 4 / 5 / 7 | 35.1 / 29 / 70 / 134 | 135.2 / 109 / 291 / 1068 | 4.2 / 3.3 / 6.8 / 112 | 30.5 / 28 / 55 / 71 | 109.3 / 105 / 195 / 285 | 4.2 / 4 / 7 / 10 | 33.3 / 33 / 37 / 42 |
| Energy-tower group in view, 3,000 units off | 54 | 5.5 / 6 / 6 / 6 | 93.4 / 96 / 96 / 96 | 332 / 338 / 349 / 356 | 3.6 / 3.6 / 3.7 / 3.7 | 53 / 53 / 53 / 53 | 213 / 213 / 213 / 213 | 6 / 6 / 6 / 6 | 41.3 / 42 / 43 / 43 |
| Energy tower close up, a tank and a fighter | 25 | 6 / 6 / 6 / 6 | 92.6 / 90 / 98 / 98 | 517.8 / 525 / 556 / 562 | 5.6 / 6.1 / 6.2 / 6.3 | 50 / 51 / 51 / 51 | 228 / 228 / 228 / 228 | 7 / 7 / 7 / 7 | 42.6 / 43 / 43 / 43 |
| Silo tunnel, flying in | 89 | 3.7 / 4 / 4 / 4 | 40.1 / 49 / 52 / 55 | 1776 / 1943 / 2450 / 2581 | 45.6 / 45.6 / 61.1 / 75 | 35.1 / 39 / 39 / 39 | 10.5 / 18 / 18 / 18 | 1.6 / 2 / 2 / 2 | 4 / 4 / 4 / 4 |
| Silo, waiting at the end | 77 | 2.2 / 2 / 3 / 3 | 0 | 0 | - | 30 / 30 / 30 / 30 | 0 | 1 / 1 / 1 / 1 | 4 / 4 / 4 / 4 |

"Pixels a line" is each frame's pixels over its lines. The runs:

- **Flight**: boot, start, hold space for 3 s, fly 30 s, cursor left
  1.5 s, fly 22 s. It's a new run of the same kind as the 704-frame one
  above, not a replay: the random numbers mix in the player's steering,
  so no two runs are alike. This one averaged 4.0 VBLs against 3.69.
- **Towers** and **close up**: fresh boots, then the player teleported as
  for the earlier screenshots (x &1EC0, z &1308 and &1C70, heading 0).
- **Silo**: a fresh boot, then teleported into a silo's box (x &1C30,
  z &DC60, heading &C10). The frames split by whether any line was drawn:
  flying down the tunnel, then stopped at its end, where the tunnel's
  vertices are still transformed but none of its edges survive the clip.

What the figures show [measured] from the table:

- In flight the lines are short: a median of 3-4 pixels, and a few
  hundred pixels a frame. Per-line, per-vertex and per-object work
  outweighs plotting except in the tunnel.
- The back-face test costs more transforms than drawing: three vertices a
  face for every face of every drawn object (213 for the six objects of
  the tower group, 71 faces), against 53 vertices transformed for drawing.
- The long lines are the tunnel's (45 pixels a line, about 2,000 a frame)
  and the lasers (the 112-pixel line in flight).
- With nothing drawn the frame still takes 2 VBLs, so the fixed work (the
  17,136-byte clear, the panel, 140 object handlers, collisions, the
  scanner) is over one VBL [inferred: the raster wait means a frame
  finished in under a VBL would take 1; a sampling profile in Hatari,
  `profile on`, would split it].

### Where the time goes

Hatari's profiler, by area [measured 2026-10-18: `tools/st_profile.py`
on `tests/st/profile_flight.txt` (33 s) and `profile_towers.txt` (8 s)]:

| | Flight | The towers |
|---|---|---|
| Drawing: lists, transforms, back-face tests, faces, projection, clips, lines, the clear | 68.0% | 76.9% |
| Ground dots (&047AA's set-up, `dot_colour`) | 8.7% | 6.4% |
| Waiting for the raster, swapping | 8.7% | 6.7% |
| Logic: flight, handlers, collisions, docking, the laser, random numbers | 6.4% | 4.2% |
| Printing the score and messages (reprinted every frame) | 3.7% | 2.6% |
| Panel: waveforms, gauges, scanner | 3.6% | 2.5% |
| Other | 0.8% | 0.8% |

Within drawing in flight: the transform and matrix 16.7%, the back-face
test's vertices 11.5%, `draw_shape`'s faces and edges 11.9%, projecting
edges 8.1%, clearing the view 6.5%, the lists 5.6%, the line drawer 3.4%.
The gunsight's bitmap is 2.2%; the handlers' loop over 140 objects, most
calling the handler that does nothing, about 2%.

### Coordinates and fixed point

- **World**: x, y, z are signed 16-bit and wrap; y is negative upwards
  (the player starts at y = -48) [measured] Hatari RAM, &0578C.
- **Angles**: 4096 to a turn; the matrix builder masks pitch and heading
  to 12 bits and roll to 9 bits times 8 [measured] &04114.
- **Sine**: `16384 sin(2 pi i / 4096)` within 2 [measured]; 2.14 fixed
  point. The object's matrix is nine 2.14 words at `$156(a6)`-`$166(a6)`,
  built from the three angles (&04114, skipped when the angles haven't
  changed) [measured].
- **Vertex transform** (&03FFE): each axis is three `muls`, each result
  shifted left 2 and its high word taken (so a 2.14 product), summed; all
  three are then shifted right 4 and the object's camera-relative position
  (`$194`-`$198(a6)`) added [measured] &03FFE-&0408C. So shape units are a
  sixteenth of world units: the pyramid mine's ±2048 base is ±128 in the
  world. The camera rotates object positions with a second matrix at
  `$168(a6)` (&04092) [measured].
- **The player**: position `$12E/$130/$132(a6)`, angles `$13A/$13C/$13E`
  (heading `$13C`), speed `$21E` [measured] &077B4. Each frame x += speed
  x S(heading) / 32768 and z += speed x S(heading + 1024) / 32768, where S
  is the table (16384 sin), so speed x sin / 2; roll = -(mouse x / 16)
  with mouse x clamped to ±&1F0 [measured].
- **Objects** (64 bytes at `$129A(a6)`, 140 of them): +0 type (0 = free),
  +2 flags (bit 7: neither lasers nor ramming destroy it), +4/+6/+8 position, +A/+C/+E
  angles (+C heading), +10 speed, +14/+16/+18 timers, +1C/+1E/+20 velocity,
  +22 in the draw list, +23 in the near list, +24 exploding, +26 explosion
  frame (0-31), +28/+2A/+2C position relative to the camera, +2E set when
  lasers can't hurt it, +30 hit points [measured] &07A54-&08390, &0A6AE,
  &087AA.

### Culling and lists (&0561C, &057B8)

1. A coarse pass over all objects keeps those within &2020 of the player
   in z, or below -&2020 in z and within &2020 in x. The test is looser
   than a box (it reads like an intended AND) [measured] &05780-&057A4.
2. Each of those is rotated into camera space (&04092) and stored at
   +28/+2A/+2C. Every one not exploding goes on the **near list** (`$98`,
   count `$240`), which the collisions and the scanner use [measured].
3. The **draw list** (`$94`, count `$23E`) takes those with camera z up to
   &2000, not wholly behind (z above minus the object's size), and
   |x|, |y| <= 2z [measured] &0581C-&05860. There's no depth sort:
   objects are drawn in list order, which works because every line is ORed.

Because the coarse test keeps the whole band within &2020 in z, whatever
x is, **about 40 objects are rotated into camera space every frame in
flight** (mean 40.1, median 40, at most 53, over 496 frames), for a draw
list of 4.4 [measured 2026-10-18: `tools/st_render.py` on a flight
captured by `tools/st_scenes.py`]. About 10 of the 40 are more than
24,600 units off in x, too far ever to be drawn; 16 are within 12,000.

What reads the camera-space positions (+28/+2A/+2C) [measured] the
disassembly: the draw loop (&0511C) and the missile view's (&05462), the
scanner (&05E1C, and the mono one at &06920), the mines' handler
(&07ACC-&07B3C), enemy fire's line (&07E6E), the collisions (&08442),
refuelling (&0854E-&0857E) and the laser's hit test (&08738).

### Drawing an object (&04B1C)

1. Type to shape through &0AC76; the shape's entry at &0AF4E + 16 x shape
   [measured].
2. The matrix from the object's angles plus the camera's (&04114).
3. **Back-face culling**: for each face, the camera-space positions of its
   first three vertices give n = (v1 - v0) x (v2 - v0); the face is visible
   if n . v2 < 0 (the viewer is at the origin looking along +z), or if face
   word +6 is negative, or if `$2BD(a6)` is set. A visible face marks its
   vertices and its edges [measured] &04BC2-&04CD4.
4. The marked vertices are transformed (&03FFE) into a table at `$2F8(a6)`,
   8 bytes each [measured] &04CD8.
5. Each marked edge goes to &04D66: near-plane clip at z = 2 (&0A374),
   projection x' = (x << `$212`) / z + `$1FC`, y' = (y << `$212`) / z +
   `$1FE` (`$212` = 7, `$1FC` = 143, `$1FE` = 68 in colour), Cohen-Sutherland
   clip to the window `$146-$14C` (16-303, 10-128) (&0A170), then the line
   drawer through `$2C(a6)` [measured].

`$2BD(a6)` is cleared at start-up (&0396C) and toggled only by H on the
Interrogate screen (&03FEA); it reads 0 in flight [measured] Hatari RAM
dump. So **flight draws each object with its back faces removed**, and the
screenshots agree (`hatari_tower.png`, `hatari_interrogate.png`)
[measured]. Objects are still see-through to each other, which is what the
manual's "Enhanced Vision System" describes.

The near-plane clipper has code for the four side planes, but it's jumped
over (&0A378, &0A3A6), so only z = 2 is clipped in 3D [measured].

**The near clip's arithmetic** (&0A4DC) [measured: `tools/st_render.py`
reproduces it, and the tunnel's lines with it]: for an edge from p (z < 2)
to q, it divides (2 - z_p) << 16 by z_q - z_p into a 16-bit quotient,
then adds (dx x quotient x 2) >> 16 to x_p, and the same to y_p, as if
the quotient had 15 bits. So the clipped point is twice as far along the
edge as the plane is; and when the plane is half way along or more, the
quotient overflows, `divs` leaves its operand alone, its low word is 0,
and the point stays where it was with z set to 2. When it's q that is
behind, the two points are swapped first and stay swapped. Flying down
the silo tunnel (106 frames) clipped 586 edges, 384 of them by the
overflow; flight clipped 2.

**The projection's divides overflow too**: x << 7 / z with the result
past 16 bits leaves the shifted x, whose low word becomes the screen
coordinate (768 times in the tunnel's 106 frames, 4 in flight). The 2D
clip then cuts whatever line that makes.

The projection centre x = 143 is the middle of a 288-pixel window starting
at x = 0; the window starts at x = 16, and the gunsight is at `$204` = 160.
So the 3D centre is 17 pixels left of the window's middle [measured]
&08CD6, Hatari RAM; the silo screenshot shows the tunnel's vanishing point
left of the sight. It reads like an offset never updated [inferred: the
mono set-up has the same 16-pixel gap doubled, 287 against 320, &08D9C,
so it was carried over rather than tuned per mode].

**Exploding objects** (&04DAC) draw each face separately, offset along its
normal by the explosion frame and dropped by a gravity table (&04FA8), in
the face's own colour [measured].

### The line drawer (&09128)

- Sorts the end points left to right, steps ±160 bytes a line, starts at
  screen + 160y + 8(x/16), with a one-bit mask in a word [measured].
- Chooses one of 16 routines by colour (`$208(a6)`), from two tables:
  &09174 for y-major lines and &091BA for x-major. Each routine is a
  Bresenham loop that ORs the mask into the bitplanes set in that colour,
  so colour 0 draws nothing [measured] &091FA.
- The colour is the face word +0. In &04B1C the edges are drawn after all
  the faces are tested, so the whole object is drawn in the **last face's
  colour**; every shape has one colour on all its faces anyway [measured]
  `st_shapes.py`.
- Lines are ORed, never erased: where two colours cross, the planes
  combine [measured] the routines; the view is cleared every frame instead.

### The clear (&099D0)

`movem.l` of twelve zeroed registers, three a line (144 bytes, 288 pixels),
then 16 bytes skipped; from screen + &5098 backwards, 3 x 30 lines in a loop
plus 29 unrolled: 119 lines, 17,136 bytes [measured]. Only the window is
cleared; the panel stays.

### Other drawing

- **Dots** (&0976E): a dot of 1, 2 or 2 x 2 pixels by distance (z below
  &1000 and &700), in the colour set by &08F3E [measured].
- **Text**: two printers per mode (&01264, &012EC colour; &01134, &01184
  mono), 8 x 8 font at &16D88 [measured].
- **The white flash** (&09D38) fills the view with colour 15 at a level
  change [measured] &026B2.

## The shapes

Format (&04B1C, &043EE) [measured]:

- **Type to shape** &0AC76: 32 words; all identity except type 6 (the
  silo), which is drawn with shape 18.
- **Shape table** &0AF4E: 16 bytes a shape: nverts, nedges, nfaces, then
  the offsets from &0B11E (`$78(a6)`) of the vertices, edges, faces and a
  fourth block the renderer stores (`$1C(a6)`) but never reads, then a word
  (always 0) stored in `$1E0(a6)`.
- **Vertex** 8 bytes: x, y, z words and a pad. A cube is ±2048.
- **Edge** 4 bytes: the byte offsets (index x 8) of its two vertices.
- **Face**: nine words, then lists. +0 colour; +2, +4 copied but never
  read; +6 negative means "always visible"; +8 to +12 unread; +14 the
  vertex count; +16 the edge count. Then the vertex indices (the first
  three, in order, give the normal) and the edge indices.
- **Animation** &043EE, every frame: seven frame lists, each (current,
  last, two words, then last + 1 vertex-block offsets). The current offset
  is written over the shape's vertex offset; the edges and faces stay. A
  counter at &0D97E steps 0-15 into the code at &06011 [measured].

Colours are the flight palette's (RESULT.TRA's, below).

| Shape | Type | Name (Interrogate screen) | Verts | Edges | Faces | Colour | Always-visible faces | Frames | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | Walker | 22 | 42 | 28 | 7 (&056) | | 16 | impervious to lasers |
| 2 | 2 | Pyramid mine | 8 | 12 | 6 | 3 (&760) | | | |
| 3 | 3 | | 8 | 12 | 6 | 1 (&700) | | | a flat red box; 20-27 a level |
| 4 | 4 | Energy Tower | 16 | 28 | 13 | 7 | | | placed in threes round a type 11 |
| 5 | 5 | | 14 | 18 | 5 | 5 (&737) | | | |
| 6 | (none) | | 14 | 25 | 10 | 6 (&077) | | | no type uses it |
| 7 | 7 | Starglider drone | 16 | 30 | 16 | 6 | | 9 | wings flap |
| 8 | 8 | Armoured Transport Vehicle | 16 | 28 | 13 | 13 (&024) | | | |
| 9 | 9 | Egron Battle Tank | 24 | 38 | 16 | 15 (&777) | | | |
| 10 | 10 | | 22 | 42 | 28 | 7 | | 16 | shares the Walker's data |
| 11 | 11 | | 4 | 2 | 1 | 15 | 1 | 20 | the energy beam between towers |
| 12 | 12 | | 9 | 16 | 9 | 1 | | | missile handler (&07D8E) |
| 13 | 13 | Bute fighter | 10 | 23 | 15 | 5 | | | |
| 14 | 14 | Diamond Proximity Mine | 10 | 24 | 16 | 3 | | | |
| 15 | 15 | Stomper | 28 | 43 | 21 | 8 (&034) | 2 | 29 | impervious to lasers |
| 16 | 16 | Skim fighter | 10 | 22 | 14 | 11 (&066) | | | |
| 17 | 17 | | 12 | 22 | 14 | 12 (&045) | | | an arch |
| 18 | 6, 18 | (silo) | 12 | 13 | 5 | 13 | | 11 | |
| 19 | 19 | | 17 | 34 | 19 | 14 (&002) | | | |
| 20 | 20 | Juno cannon | 10 | 15 | 7 | 5 | | | |
| 21 | 21 | Lotus Starfighter | 13 | 23 | 12 | 6 | | | |
| 22 | 22 | (silo tunnel) | 30 | 54 | 1 | 15 | 1 | | the docking interior |
| 23 | 23 | Tri-launcher | 18 | 21 | 4 | 15 | | | |
| 24 | 24 | Egron Neutron Missile | 9 | 15 | 7 | 1 | 1 | | |
| 25 | 25 | Egron Homing Missile | 15 | 22 | 10 | 15 | 1 | | |
| 26 | 26 | Pyramid Launcher | 8 | 12 | 1 | 15 | 1 | 35 | |
| 27 | 27 | StarGlider One | 24 | 41 | 19 | 4 (&730) | 1 | 37 | wings flap |
| 28 | 28 | (GAME OVER) | 125 | 125 | 3 | 15 | 3 | | the words, in 3D |

[measured] `st_shapes.py`; names from the Interrogate list (&02B98, names
via &02C4C); the notes from the handlers and level lists. The names in
brackets are [inferred] from where the game uses them (&085E6 for the
tunnel, the collision code's type 6 for the silo, the screenshots).

## The game

*`st-logic.md` (and `st-logic.json`) is the full inventory of the game's
logic, routine by routine, with every variable and object field and the
corrections to what follows here; where they disagree, it's the later
reading, and the more careful.*

### The world

- 16-bit coordinates wrap in x and z: a torus of 65,536 units, which at
  &290 units a sector is the manual's 100 x 100 sectors of Novenia
  [measured] `init_objects` multiplies the layouts' sector numbers by &290;
  the player starts at sector 50, 50 (shown in the panel).
- **Layouts** (&17C88, indexed by the level `$296(a6)`, which starts at
  1, &03A1E): level 1 uses &17D40 (82 objects), level 2 &17FD8 (89),
  level 3 &182A8 (97), levels 4 and up &185B8 (114); entry 0 repeats
  entry 1. An entry is four words: type, sector x, sector z, and the hit
  points (+30) [measured].
- `init_objects` (&0A6AE) clears the 140 records, keeps the first ten
  for missiles (a stack of pointers at &94C, its top in `$9C(a6)`, the
  count in `$25C`), copies the layout from the eleventh, and gives types
  7, 27, 21, 20, 1, 15, 8, 9, 2, 14, 13, 16, 5, 17, 3, 4 and 6 set-up code
  (&0A894-&0AA82) [measured]. Each energy tower becomes three towers, one
  at the layout's point and two 4,000 units on in z, 512 apart in x, with
  a type-11 beam midway [measured] Hatari RAM dump of level 1.
- Level 1 in RAM (Hatari): 107 objects with the extras; four silos with
  heading 1008; the commonest is type 3 (27) [measured].

### Progression and score

- The score is a BCD long at &0150C, eight digits [measured] &00E10.
- The level goes up by one each time the score's second byte (the
  ten-thousands) changes, to at most 34 (&0503C). The world is then
  re-populated from that level's layout and the view flashes white
  [measured] &01F06, &026B2.
- **Laser kills** score from &0AE9A, **missile and ramming kills** from
  &0AED6 (BCD) [measured]:

| Type | Laser | Missile/ram | | Type | Laser | Missile/ram |
|---|---|---|---|---|---|---|
| 1 Walker | 0 | 1500 | | 15 Stomper | 150 | 1750 |
| 2 Pyramid mine | 50 | 150 | | 16 Skim fighter | 250 | 550 |
| 3 | 50 | 50 | | 17 | 150 | 150 |
| 4 Energy Tower | 50 | 100 | | 18 | 300 | 750 |
| 5 | 50 | 50 | | 19 | 200 | 200 |
| 6 silo | 50 | 50 | | 20 Juno cannon | 400 | 800 |
| 7 Starglider drone | 500 | 850 | | 21 Lotus Starfighter | 290 | 600 |
| 8 ATV | 100 | 250 | | 22 | 200 | 200 |
| 9 Battle Tank | 200 | 350 | | 23 Tri-launcher | 200 | 410 |
| 10 | 100 | 100 | | 24 Neutron Missile | 5 | 50 |
| 11 beam | 100 | 100 | | 25 Homing Missile | 10 | 100 |
| 12 | 100 | 100 | | 26 Pyramid Launcher | 275 | 450 |
| 13 Bute fighter | 120 | 500 | | 27 StarGlider One | 0 | 7500 |
| 14 Diamond mine | 500 | 500 | | | | |

- The end screen rates the pilot from shots fired, hits, dockings and hits
  taken: ABOVE AVERAGE, ACCURATE, SUPER FLYER, ACE PILOT, COMMANDER, or
  CHEAT!?! (&08AC3-&08C50) [measured] strings; the formula is open.
- A ten-entry high-score table ("STAR SCORES") [measured] &01A1C, &00E10.

### The player

- **Energy** `$25E(a6)`: drains by speed / 16 each frame; at 0, "POWER
  DRAINAGE TOO GREAT!" ends the game. **Shields** `$260`: at 0, "SHIELD
  DEPLETED, AGAV DESTROYED!". **Laser energy** `$28A`: &100 a shot. All
  three are 16-bit, full at &FFFF [measured] &0204E-&02156, &0866C.
- **Scraping the ground**: moving within 20 units of the ground (y >= -20),
  shields lose 300 a frame (effect 3) [measured] &02072-&0209A.
- **Laser** (&0866C): fired by key-state slots &74, &1C (Return), &52
  (Insert) or &72 (keypad Enter) [measured]. &74 is the left mouse button:
  start-up sends the IKBD command 7 with 4, "mouse buttons act like keys",
  and then "LEFT=0x74 & RIGHT=0x75" [source]
  https://www.kernel.org/doc/html/latest/input/devices/atarikbd.html.
  The bolt takes 4 frames (counted more slowly when fewer than 6 or 3
  objects are in view); two cyan (colour 6) bolts close from (-64, 150) and
  (384, 150) on the sight. Then the first object in the draw list whose
  projected collision box contains the sight is hit: 1 from +30, and below
  0 it explodes and scores [measured] &086D4-&08850.
- **Sight** (`$244/$246`): floats with the steering (x = 160 + mouse x / 4,
  y = 68 - mouse y / 8) unless F has fixed it [measured] &079BC.
- **Missiles**: up to two (`$278`), picked up with P in a silo; L launches
  one and the view follows it ("MISSILE VIEW") until it hits [measured]
  &02982, &0295A, &05248.
- **Flight keys**: bank with cursor left/right, X/C or the defined keys;
  climb and dive with cursor up/down, ;/. or the defined keys;
  accelerate with space or the defined key; brake with / (&0270E)
  [measured]. The six defined keys come from the K screen (&022BA).
- **Command keys**: F fixed sight, L launch missile, P pick up missile,
  I interrogate (docked), Q sound off, S sound on, ESC quit [measured]
  &0270E-&02A44.
- **The cheat**: DEL then J, S, space, A, R, G, twice; if the sight is
  fixed and the craft stopped, the second time refills energy, shields and
  laser and toggles cheat mode (`$2CD`) [measured] &02894-&0292C. Cheat
  mode holds energy, shields and laser at &55F0, &9C40 and &7530 every
  frame (&02036), lets P take a missile anywhere, and enables M (freeze
  enemies), N (+5000) and G on the title (the model viewer) [measured].

### Enemies (handlers &08252, by type; entries 31-61 repeat 0-30)

[measured] the handlers; "near" means within 1,000 units in x and z.

- **&07AA0, nothing**: types 0, 4 (towers), 5, 17, 22, 31.
- **&07AAE, the silo** (6): turns 16 a frame; every 2,000 frames a
  missile is ready (+14 set).
- **&07AC6, mines** (2, 14): spin, bob up and down; in the draw list and
  within &800 in z, "WARNING: MINE DETECTED"; within &600 it explodes:
  shields -15,000, "MINE HAS JUST EXPLODED!", colour 0 flashes &333.
- **&07BF4, fighters and walkers** (1, 10, 13, 15, 16, 18, 21, 27): move
  by velocity. Near: 1 frame in 128 fire the laser, 1 in 8 try a missile
  (if aligned), otherwise turn a sixteenth of the way towards the player
  (bearing from &08390). Far: 1 in 128 fire, 1 in 32 turn towards the
  player, 1 in 16 try a missile. StarGlider One, near: 1 in 64 fire,
  otherwise turn, and now and then try a homing missile.
- **&07CA4, wanderers** (7, 8, 19): move; 1 in 64 frames turn by up to
  ±16; 1 in 16 fire.
- **&080D8, the tank** (9): near, turns to the player and sometimes
  launches missiles; far, circles and drives.
- **&08174, Juno cannon** (20): in the near list, 1 frame in 8 launches a
  missile (no alignment test), otherwise turns towards the player.
- **&081AA, Pyramid Launcher** (26): spins; except on level 1, 1 frame in
  16 launches a homing missile.
- **&081F4, Tri-launcher** (23) and &081D6: spin, and try a missile
  (aligned) only while the player carries one (`$278` non-zero).
- **&0821A** (3): near, fires 1 in 32 frames.
- **&08232, the beam** (11): from level 3, 1 in 2,048 frames it goes out.
- **&07D8E, neutron missile** (24, 12): flies its velocity, homes on the
  player's altitude by 1/8 a frame, explodes when its life (+14) runs out.
- **&07DD2, homing missile** (25): homes on altitude by 1/4 and re-aims
  at the player every frame; explodes above y = -1700 ("unstable at high
  altitudes", as its description says).
- **&0834A** (28-30, GAME OVER): adds 1 to colour 0 every frame.

**Enemy fire** is an instant hit (&07E18): shields -300 (-100 on level 1;
table &0AE5E), a red line from the attacker to a random point on the
bottom of the view, colour 0 flashes &020 (green), and the hit count goes
up. Aligned attackers (within &50 of the bearing) take a free slot for a
missile: type 24, or 25 from level 2 [measured] &07EDC.

**Ramming** (&08416): within a type's box (x and z from &0ACB6, y from
&0ACF2, camera-relative), the object explodes unless +2 bit 7 is set, and
shields lose &0AE1E[level][type]: 3000 on level 1, 5000 on level 2,
7500 from level 3 (1000 for silos), and colour 0 flashes &555. Walkers and
stompers cost a further 8000 and survive; StarGlider One only takes damage
from the player's missile [measured] &084DA-&08518, &020BA-&0213C.

**Random numbers**: &04692 (32-bit shift-and-EOR with &1D872B41, plus the
mouse x accumulator and `$5C`) and &046B2 (lagged additive on
`$5C-$61(a6)`). Both mix in the player's steering, so play depends on
input [measured].

### Silos, refuelling and energy

- **Docking** (&085AC): fly into a silo (type 6) inside its box (±360 in
  x and z, ±180 in y) with your heading within ±&154 of the silo's. The
  shields refill (&FFFF), the docking count goes up, and the view becomes
  the tunnel (objects &1218 and &1258, the second the silo's missile, taken
  by flying into it or with P) on colour 0 = &036: "DOCKING, PRESS I FOR
  INTERROGATE". At the end of the tunnel the craft stops and the lasers
  refill; then "Lasers and Shields replenished. Press SPACE BAR to launch,
  or I to Interrogate computer.", and the second speech clip plays every
  256 frames while it waits [measured]
  &085CE, &05672, Hatari (teleported into a silo's box with the debugger).
- **Interrogate** (I, docked): the 17 known objects, each spinning, with
  its name and two lines of description; H hidden lines, X/S Y/T Z/A
  rotate, L/K zoom, 8/2/4/6 move, R/E reset, SPACE next, E exit
  [measured] &02A44-&02B70, &03DB8.
- **Refuelling** (&0851C): fly through a type-11 beam (z &79E-&7D0,
  heading &60C-&9F4 relative, |x| < &2BC): energy +&190 a frame, colour 0
  &500, "ENERGY CELLS REFUELLING" [measured].

### The cockpit

RESULT.TRA is the cockpit [measured]: the flight screenshot's palette and
panel match it, and every frame clears the 288 x 119 window over its side
walls. Docked and on the end screen the whole picture shows.

- **Scanner** (&05E0C): each near-list object within ±&2000 of the camera
  in x and z, a dot at (160 + x/512, 164 - z/512) in a colour per type
  (&06006) [measured].
- **Waveforms** (&05872): two 16 x 8 pre-drawn animations of 16 frames
  (&06D2A, &06D6A), copied to screen offsets &6110 and &6148 (y = 155,
  x = 96 and 208), one frame further on each rendered frame [measured].
  They're decoration.
- **Gauges**: bars drawn from about &05C46 [inferred: the code clears and
  ANDs panel words in columns; the bars' meanings want a check by poking
  energy and shields in Hatari].
- **Numbers**: the score top left; the last kill's score top right
  (`$286`, &05060); the sector coordinates bottom centre (x/&290, z/&290,
  &06984 in the mono path) [measured]. Bottom left is the missile count:
  1 at the start, 2 after flying through a silo's missile [measured]
  `hatari_flight.png`, `hatari_silo_menu.png`. What the red digit and the
  green letter at the top centre show is open (a heading, "N", at a
  guess).

## The screen

- **Mode**: low res, 320 x 200, 16 colours, four interleaved bitplanes,
  160 bytes a line [measured] &0493A, the line drawer. On a mono monitor it
  runs in high res: window 32-607 x 20-257, shift 8, centre (287, 136)
  [measured] &08D84.
- **The view**: x 16-303, y 10-128 (288 x 119) [measured] `$146-$14C`,
  the clear, the screenshots.
- **Double buffer**: &70000 and &78000 [measured] &0A56E.
- **Palettes** [measured] `st_tra.py`, Hatari screenshot colours:

| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Flight (RESULT.TRA) | 000 | 700 | 070 | 760 | 730 | 737 | 077 | 056 | 034 | 014 | 003 | 066 | 045 | 024 | 002 | 777 |
| Title (TITLE.TRA) | 000 | 720 | 003 | 004 | 006 | 007 | 037 | 047 | 300 | 400 | 500 | 600 | 700 | 761 | 555 | 777 |
| Start-up (&08E82) | 000 | 700 | 007 | 520 | 555 | 077 | 707 | 770 | 555 | 070 | 005 | 050 | 222 | 055 | 505 | 550 |

  The game fades between palettes (&06ACC). Colours 7-14 of the flight
  palette are the cockpit's blues; the shapes use 1, 3-8 and 11-15.
- **Colour 0 flashes** (`$242`, written at each frame end): &020 enemy
  laser hit, &333 mine, &222 laser kill, &036 docked, &500 refuelling, &040
  missile picked up, &555 ramming [measured] the writes to `$242`.
- **.TRA format**: 32,144 bytes: a 144-byte header (+0: a 16-byte colour
  map for the mono path; +&14: the palette, 16 words) then 320 x 200 4-bit
  chunky pixels, two to a byte, left pixel in the high nibble, which the
  game converts to planes as it loads (&0AACA) [measured]. The title is
  `title_tra.png`, the cockpit `result_tra.png`.

## Sound

### Samples

| Sample | Block | Header | Plays | At | Seconds | Started by |
|---|---|---|---|---|---|---|
| clare1 | &18DB4 | 7030 at 6000 Hz | 7040 bytes | 6144 Hz | 1.15 | L, launching a missile (&029A2) |
| clare2 | &1A934 | 7348 at 6000 Hz | 7424 bytes | 6144 Hz | 1.21 | docked and rearmed (&056BA) |
| clare3 | &1C634 | 5654 at 6000 Hz | 5760 bytes | 6144 Hz | 0.94 | shields below &2EE0, every 128 frames (&01F5A) |
| clare4 | &1DCB4 | 6842 at 6000 Hz | 6912 bytes | 6144 Hz | 1.12 | energy below &2EE0, every 128 frames (&01F9C) |
| star | &1F7B4 | 179168 at 10000 Hz | 179200 bytes | 9830 Hz | 18.23 | the title, looped; the end screen (&02290) |

[measured] `st_samples.py`. Each block is the .snd file as it was: a long
(the sample count) and a word (the recording rate), then signed 8-bit
samples, flipped to unsigned at start-up. The played lengths are the gaps
between blocks, so each play includes the next header [measured].

**Playback** (&01A50, &01AF8): the YM's mixer is set to &3F (tones and
noise off) and the periods to 0; then Timer A (MFP control 4, divide by 50:
49,152 Hz, divided by the data, 8 for speech, 5 for the song) interrupts at
the sample rate. Each interrupt reads one byte through a self-modified
`move.b $12345.l,d0` (the address at &01B00 is the pointer), looks up three
volumes in the table at &01B4A (256 bytes each for channels A, B and C) and
writes registers 8, 9 and 10 with three `movep.w` [measured]. The MFP
rates: the dividers 4, 10, 16, 50, 64, 100, 200 for control values 1-7 and
the 2.4576 MHz timer clock, as Hatari models them [source]
https://github.com/hatari/hatari/blob/main/src/mfp.c (`MFPDiv`) and
`src/clocks_timings.c` (`ATARI_MFP_XTAL`).

What Clare says in each clip is [inferred] from where it plays: missile
launched, docked/rearmed, shields low, energy low. Listen to check:
`st_samples.py PRG --wav DIR` writes them.

### Music and effects

The only music found is the sampled title song: none of the reached code
or the effect routines' entry points looks like a tune player [inferred:
check by tracing YM writes (`--trace psg_write`) through a game]. In play, effects
come from `sfx_start` (&00110, effect number in d0): 24 effects in the
table &01854, each a routine and a parameter block: &004A8 (0-3), &0071E
(4-7), &0052E (8-11, 17), &002C8 (12-15), &00180 (16, 19), &00626 (18,
20-23) [measured]. They drive the YM from Timer A (e.g. &00180 installs
&00228) and are skipped while a sample plays or with sound off (`$2CB`).
Effects used: 0 enemy laser hit, 1 mine and ramming, 2 laser hit, 3
scraping the ground and the launch countdown, 8 the cheat prompt and
refuelling, 9 the cheat's end, &10 docking, &14 laser fire and the
Interrogate keys [measured] the `sfx_start` calls. How each routine shapes its sound is open.

## Running it in Hatari

Hatari (git, 2026-10-17, `6c80daaf`) was built in `/home/matthew/dev/hatari`
(`cmake .. && make`) with EmuTOS 1.3 (`etos256uk.img`) [measured]. Hatari
also created `~/.config/hatari/hatari.nvram`. To reproduce:

```sh
tools/st_hatari.py SCRIPT --disk "original/st/Starglider (1987)(Rainbird).stx" \
    --hatari ../hatari/build/src/hatari \
    --tos ../hatari/emutos/emutos-256k-1.3/etos256uk.img --out /tmp/run
```

with a script such as:

```text
wait 38            # boot to the title (about 1,750 VBLs)
key 57             # space: start
wait 4
debug b pc = $19880 :trace :quiet :file /tmp/run/frame.ini   # frame_end; frame.ini holds "e VBL"
debug w w $5c02e $1c30 $ffd0 $dc60   # player x y z into a silo's box
debug w w $5c03c $0c10               # heading
shot docked
```

- Use the `.stx`: the TOSEC `.st` halts at the protection check.
- **Profiling** (`tools/st_profile.py`): Hatari's `profile save` writes
  nothing when sent through the command FIFO, because only entering the
  debugger processes the profile. The Hatari in `../hatari` is patched to
  process it on saving: in `src/debug/profile.c`, `Profile_Save` calls
  `Profile_CpuStop()` before writing a CPU profile.
- `--fastfdc off` (the driver's default) is needed for the STX.
- Fast-forward skips rendering, so screenshots come out black; the driver
  runs in real time.

## Open questions

1. **The sound-effect routines** (&00180-&00A9E, table &01854): how each
   shapes the YM; capture the register writes in Hatari
   (`--trace psg_write`) for each effect number.
2. **The gauges and the top-centre readout**: which bar is which, and
   what the red digit and green letter show. Poke energy, shields and
   laser energy in Hatari, turn, and watch the panel.
3. **The right mouse button**: with buttons as keys it should arrive as
   key &75, yet the ACIA handler steers mouse y into the speed when a
   packet's button bit is set (&00C88). Trace the ACIA bytes in Hatari
   while clicking to see which path runs.
4. **The rest of the level-load set-up** (&0A894-&0AA82). Read so far
   [measured]: the drone (7) flies at y -500, speed 250; StarGlider One
   (27) at y -750, speed -300, 4 hit points (5 missile hits), lasers
   can't hurt it; walkers (1) speed 20 and stompers (15) speed 16, lasers
   can't hurt them; towers (4) and types 5 and 17 are indestructible
   (+2 = &FF); the mines get random bob timers; type 9 starts heading &400
   at speed 64. The rest (21, 20, 8, 13, 16, 3, 6 and the tower expansion
   at &0A9B0) wants the same reading.
5. **Types 3, 5, 12, 17, 19** have no description. Their handlers and
   counts are above; the manual or the novella may name them.
6. **The pilot rating formula** (&08A0A-&08C50).
7. **What the &60000/&68000 slots swapped with the screens are for in
   flight** (&0A56E): read them in Hatari mid-flight.
8. **The ground dots** (&047AA): the pattern and its spacing.
9. **The code not yet reached** (about 14K of the code area): mostly the
   sound routines, the printers and the high-score entry; add roots to
   `st_star.ctl` as they're identified.
