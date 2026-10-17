# The BBC Master 128: what the port can afford

What a Master 128 can spend on drawing and erasing wireframe, how much memory a game has around a
double-buffered screen, and what sampled sound costs. Every figure is tagged:

- **[measured]**: run or read by us, with the tool or file named.
- **[source]**: someone else's published figure, linked.
- **[inferred]**: our arithmetic, shown.

"Cycles" are 2MHz CPU cycles. One 50Hz field is 39,936 cycles **[source:
[port kit hardware-facts §8](https://github.com/kieranhj/beeb-port-kit), 312 lines × 128]**. Two
fields (25fps) are 79,872 cycles, and three (16.7fps) are 119,808.

The line and clear timings were run on jsbeeb's Master 128 model (MOS 3.20, `../jsbeeb` at
68edac26) by `tools/beeb_linebench.sh` and `tools/beeb_soundbench.mjs` (see [Tools](#tools)).
jsbeeb's timing is trusted on Matt's Master for the earlier ports
(`../porting-to-the-beeb.md`), but nothing here has been run on hardware.

## Summary

| Quantity | Figure | Tag |
|---|---|---|
| Line, MODE 1 256×160, best routine (ours, NJ-style, EOR, 3 colours) | 30.6 c/px on long random lines; **39.0 c/px (824 c a line) on short 4-40 px edges**; 178 c for a one-pixel line | measured |
| Line, MODE 4 256×160 (1bpp), best (NJ + Hamiltonian) | 26.5 c/px long; **39.1 c/px (826 c a line) short** | measured |
| Line, MODE 2 128×160, Eben's raster.s (AND/ORA, not EOR) | 45.9 c/px long; **49.5 c/px (985 c a line) short** | measured |
| Line, Elite: cassette LOIN (1bpp) / Master LOIN (MODE 1 style) | 45.9 / 39.7 c/px long; 58.7 / 50.5 c/px short | measured |
| Clear, STZ abs,X down 256-byte columns | 5.13 c/byte: 10K = **52,481 c** (1.31 fields); 5K = 26,881; 20K = 104,192 (2.6 fields) | measured |
| Erase by EOR redraw | the same as drawing the old lines again | measured (same routine) |
| MODE 1 256×160, all CPU to lines, EOR erase | 25fps: **1,024 px** (about 49 edges of 21 px); 16.7fps: **1,536 px** (about 73) | inferred |
| MODE 1 256×160, all CPU to lines, full clear | 25fps: 702 px (33 edges); 16.7fps: 1,726 px (82 edges) | inferred |
| MODE 4 256×160, all CPU to lines | EOR: 1,021 / 1,532 px; clear: 1,355 / 2,377 px (25 / 16.7fps) | inferred |
| Free RAM beside two 20K screens (main + shadow) | ~10.7K low + 8K HAZEL + 4K ANDY + 64K sideways = **~87K**, of which ~23K is never paged | source + inferred |
| Free RAM beside two 10K screens (256×160 MODE 1/2) | ~87K + 20K left in &3000-&7FFF = **~107K** | inferred |
| Sample player, User VIA T1 IRQ, one latch byte a sample | **86 c a sample**: 17% of the CPU at 4kHz, 26% at 6kHz, **34% at 8kHz**, 47% at 11kHz | measured |
| Sample player, two 4-bit samples a byte | 105 c a sample: 21% / 32% / 42% / 58% | measured |
| 15 s song, 4-bit packed | 30,000 bytes at 4kHz, 45,000 at 6kHz, 60,000 at 8kHz (unpacked: double) | inferred |
| 3 s of speech, 4-bit packed | 6,000 / 9,000 / 12,000 bytes at 4 / 6 / 8kHz | inferred |

Three things stand out:

- **On short edges the per-line set-up dominates.** At 4 pixels a byte, MODE 1 draws a 21-pixel
  edge as fast as MODE 4 does at 8. A typical edge costs about 800 cycles.
- **A full clear of a 10K view costs more than a field.** EOR redraw is the cheaper erase below
  about 1,350 pixels a frame (52,481 / 39.0).
  - At 25fps the whole budget (1,024 px) is below that, so EOR always wins.
  - At 16.7fps a scene of over 1,350 px is better served by the clear.
- **Sampled speech during play costs a quarter to a third of the CPU** at 6-8kHz.

---

## 1. Prior art

### Elite (Acornsoft, 1984; Mark Moxon's annotated source at [bbcelite.com](https://www.bbcelite.com))

**Cassette and disc.** The line routine is LOIN (`elite-source.asm`, LOIN).
- **Screen.** It draws on a MODE 4 cut to 32 columns: 256 px wide at 1bpp, 256 bytes a character
  row at &6000 **[measured: source]**. A character-row step is one INC or DEC of the high byte, a
  byte step is `ADC #8` on the low byte, and `(SC),Y` never crosses a page.
- **Slope.** An 8-bit fraction, minor/major × 256, from an 8-pass shift-and-subtract divide
  (about 150-175 cycles). An accumulator S starts at 128 **[measured: source, LIL1/LIL4]**.
- **Loops and plotting.** It draws left to right (shallow) or upwards (steep) after a swap, in four
  loops. Plotting is EOR, and one end point is left unlit so that EOR-drawn polylines don't cancel
  at shared vertices **[measured: jsbeeb, every line lights max(|dx|,|dy|) pixels]**.
- **Inner loops.**
  - Shallow (LIL3): `LDA R / EOR (SC),Y / STA (SC),Y / LSR R / BCC / LDA S / ADC Q / STA S / BCC /
    DEX / BNE`, 39 c a pixel before byte and row steps.
  - Steep (LIL5): 36 c **[measured: source]**.
- **In jsbeeb:** 45.9 c/px on long random lines, 58.7 c/px on short ones, 365 c for a
  zero-pixel line **[measured]**. Five of 408 test lines put a pixel 1.0-1.23 px off the true
  line, because the 8-bit slope is inexact.

**Erasing (cassette and disc).** Each ship keeps a line heap of the lines it last drew.
- The ship is erased by EOR-redrawing the whole heap, the heap is rebuilt, and it is redrawn
  **[measured: source LL9, LL155]**.
- The ship is missing for the whole visibility and clip phase between the two, which is Elite's
  flicker **[inferred from source]**.
- The planet is erased by redrawing its circle-segment heap. The sun keeps a half-width per row
  and EORs only the difference between old and new spans. Stardust is redrawn at its old position
  to erase it, then drawn at its new one **[measured: source]**.
- No BBC version double-buffers. For the Master, bbcelite says "there still isn't enough free
  memory to maintain two copies of the screen"
  **[source: [Master memory map](https://elite.bbcelite.com/deep_dives/the_elite_memory_map_master.html)]**.

**Frame rate.**
- bbcelite gives no figure. Fairbank and Moxon give "about 5 to 10 fps … around 8 fps on a
  standard BBC Micro" **[source:
  [Essex repository](https://repository.essex.ac.uk/43577/1/CoG_EliteCraterMeridianPlanets-1.pdf)]**.
- The flight loop isn't locked to VSync: DELAY only runs outside the space view **[measured:
  source]**. The game's speed therefore varies with the load
  **[source: [Alioth wiki](https://wiki.alioth.net/index.php/BBC_Micro)]**.

**6502 Second Processor version.** The 3MHz parasite does the maths and game logic. The I/O
processor (the BBC itself, 2MHz NMOS) still draws every line.
- **Protocol.** The parasite sends OSWRCH 129, a count, then coordinate bytes. A ship's whole heap
  goes as one batch, and other lines are buffered up to 250 bytes **[measured: source
  `elite-z.asm` BEGINLIN/ADDBYT]**.
- **Overlap.** OSWRCH returns at once, so drawing overlaps the next frame's maths **[source:
  [6502SP Tube communication](https://elite.bbcelite.com/deep_dives/6502sp_tube_communication.html)]**.
- **Screen.** The space view is a 4-colour MODE 1-style screen **[source:
  [split-screen mode](https://elite.bbcelite.com/deep_dives/the_split-screen_mode.html)]**.
- **Speed.** The only speed figure found is "approximately 20% faster" **[source: Alioth wiki]**.

**BBC Master version.**
- **Screen.** It keeps a single screen, 4 colours, 256 wide with 512-byte rows, in shadow RAM at
  &4000. LOIN wraps every line in two ACCCON writes: `&0F` (D, E, X and Y: the CPU sees shadow)
  for the drawing, then `&09` (D and Y: display shadow, HAZEL paged) **[measured: source, and the
  bytes of BCODE at &1728]**.
- **Speed tricks.** The slope's divide uses log and antilog tables. The shallow loop is unrolled by
  pixel position, with self-modified `LDA #mask` immediates that carry the colour **[measured:
  source]**.
- **Ships.** Drawing is flicker-free, a line at a time: draw the new line, swap it into the heap,
  EOR-erase the old one (LSPUT) **[measured: source]**. bbcelite credits this to Apple II Elite
  **[source: [flicker-free ship drawing](https://elite.bbcelite.com/deep_dives/flicker-free_ship_drawing.html)]**.
- **Memory and CPU.** Sideways bank 6 holds blueprints and text, HAZEL the filing system
  **[source: memory map above]**. It uses 65C02 instructions (STZ, PHX/PLX, BRA) **[measured: grep
  of source]**.
- bbcelite says it "doesn't enjoy the same speed increase … as the 6502 Second Processor version"
  **[source: [bbcelite Master](https://elite.bbcelite.com/master/)]**.
- **In jsbeeb, called in place in Moxon's BCODE build:** 39.7 c/px long, 50.5 c/px short, 131 c
  for a zero-pixel line **[measured]**. The log-table slope puts pixels up to 2.9 px off the true
  line on long lines (70 of 408 test lines had at least one pixel over 1 px off).

### Aviator (Geoff Crammond, Acornsoft 1983; [aviator.bbcelite.com](https://aviator.bbcelite.com))

- **Screen.** Standard MODE 5 (160×256, 2bpp) at &5800, shown in two colours. The two bitplanes
  are two buffers **[measured: source `SetupScreen`, DrawCanopyView]**.
- **Draw, flip, erase.** New lines are ORed into the hidden plane, then the palette is swapped to
  show it. The old plane is erased by redrawing its cached lines with the opcode self-modified from
  `ORA (P),Y` to `AND (P),Y` and a constant plane mask. The result is double-buffered and
  flicker-free on one 10K screen **[measured: source ModifyDrawRoutine, EraseCanopyLines; source:
  [colour cycling](https://aviator.bbcelite.com/deep_dives/flicker-free_animation_through_colour_cycling.html)]**.
- **Line loop.** It gathers a byte's run of pixels in X and does one read-modify-write a byte,
  about 82 c per 4-pixel horizontal byte (20.5 c a MODE 5 pixel) **[measured: source, agent's
  count]**.
- **Frame rate.** Each main-loop pass is held to at least 9 centiseconds, so at most 11.1fps
  **[measured: source CheckTimePassed]**.
- **The idea transfers.** In a 16-colour mode, two planes per buffer give 3 colours + black on
  each of two palette-switched "screens" in one 20K MODE 2 screen **[inferred]**.

### Revs (Crammond, Acornsoft 1985; [revs.bbcelite.com](https://revs.bbcelite.com))

- **Screen.** A shortened MODE 5, 160×208, with palette splits on a User VIA timer
  **[source: [custom screen mode](https://revs.bbcelite.com/deep_dives/hidden_secrets_of_the_custom_screen_mode.html)]**.
- **Drawing.** Filled, not wireframe. Edges go into "dash data" blocks, which are copied to the
  screen with span fill and zeroed as they go, on a single buffer
  **[source: [drawing the track view](https://revs.bbcelite.com/deep_dives/drawing_the_track_view.html)]**.
- **Cost.** The copy is 15-25 c a byte: at least ~46K cycles for the 77×40-byte track view
  **[inferred from source DRAW_BYTE]**. No published frame rate.

### Other BBC and Electron 3D

- **Starship Command** (Peter Irvin, 1983) is 2D, with rotated arcs drawn pixel by pixel **[source:
  [StarshipCommand2022](https://github.com/TobyLobster/StarshipCommand2022)]**.
- **Star Wars** (Domark/Vektor Grafix, 1987-88) is wireframe on the BBC and Electron. Reviews call
  it slow "when there is a lot of action" and "sluggish" on the Electron
  **[source: [everygamegoing](https://everygamegoing.com/larticle/Star-Wars-000/18158)]**. There's
  no technical write-up.
- **Phantom Combat** (Doctor Soft, 1986) has "four colour line graphics" **[source:
  [everygamegoing](https://everygamegoing.com/larticle/Phantom-Combat-000/39165)]**.
- **The Sentinel** is filled and is disassembled at [thesentinel.bbcelite.com](https://thesentinel.bbcelite.com).
- No other documented frame rates were found. Stardot blocks automated fetching, so its threads
  weren't read.

### Rich Talbot-Watkins: [boom](https://github.com/waitingforvsync/boom) (2025)

A portal engine, filled by EOR. The README says only "A portal engine for the BBC Micro".

**Screen.**
- MODE 5 pixels (ULA &C4) cut to R1=32, R6=16: 128×128, 4K a buffer, plus a 3-row HUD.
- Buffers at &1800 and &7000, main RAM only. R12 is set by a T1 interrupt locked cycle-exact to
  VSync, just before the top of the screen. The HUD is a vertical rupture with its own palette
  **[measured: source `entry.6502`, `irq.6502`]**.

**Edges (`drawline.6502`).**
- Not wireframe lines: one EOR transition per x column for the fill.
- Steep edges cost ~71 c a column. Shallow ones are built a byte at a time from pre-drawn blocks,
  ~31 c a column when flat and ~52 near 1:1 **[measured: source, agent's count]**.

**Fill and clear.**
- The routines are generated at start-up. The fill is `EOR abs,X / STA abs,X` down each column,
  9 c a byte: 37,568 c for 4K. The clear is 16 × `STA abs,X`: 21,760 c for 4K **[measured:
  source, agent's count]**.
- That is ~59K cycles fixed a frame for a 128×128 window, whatever is in the scene
  **[inferred]**. An EOR fill also needs a zeroed buffer, so the clear can't be skipped.

### Eben Upton

| Engine | Machine | Screen | Buffers | Erase | Rate |
|---|---|---|---|---|---|
| [doom](https://github.com/ebenupton/doom), wireframe E1M1 | B + 48K sideways RAM | MODE 4, R1=32, R6=20: 256×160, 5K | &5800 / &6C00, R12/R13 | full clear (20 × STA abs,Y: 26,880 c), hidden behind a queue of pending plots | "roughly 7 frames per second" [source: README] |
| [lander](https://github.com/ebenupton/lander), Braben's Lander | B or Master + 64K sideways RAM | MODE 1 (dither) or MODE 2, R1=64, R6=20: 256×160 or 128×160, 10K | &3000 / &5800, R12 only | never clears: a per-column top/bottom record per screen, blacking only what's left | "about ten frames a second", capped at 12.5 [source: README] |
| [virus](https://github.com/ebenupton/virus), Zarch prototype | stock B (a 65C02 build is optional) | MODE 2, R1=64: 128×160, 10K | &3000 / &5800, R12/R13 | page-parallel clear bounded by the dirty height | capped at 25fps; README profile: clears ~20%, rasteriser ~13%, ~21% idle [source] |
| [beebgame](https://github.com/ebenupton/beebgame) | B + 64K SWR, or Master | MODE 1, hardware-scrolled | Master: the same &3000-&7FFF in main and shadow | sprites | flips at 25Hz at most |

All figures in this table are **[measured: source, agent's read]** unless tagged.

- **doom's lines.** NJ's routine, OR-plotted and retargeted to 256 wide
  (`src/boot/raster/nj-linedraw4-or.s`).
  - Shallow: 5 c a pixel between y-steps, 42 c a y-step. Steep: 26 c a pixel.
  - Vertical lines, ~70% of its pixels, use 160 unrolled `TYA / ORA abs,X / STA abs,X` blocks,
    11 c a pixel.
  - System VIA T1 free-runs one field long as a beam clock.
- **lander's fills.**
  - The landscape is traced run-slice into per-pixel y tables (division tables give the run
    lengths), then filled through unrolled `STA abs,Y` tables entered by JMP and ended by a planted
    RTS: 7.5 c a byte with a 2×2 dither.
  - The ship is pre-rotated and pre-rasterised, 13 pitches × 32 directions.
  - A VideoNuLA is detected by timing (`src/menu.bas`, BASIC lines 50-110 and 240). It sets the CRTC to 2MHz
    through &FE20 and times 5 fields, then writes &44 to &FE22. Without a NuLA, &FE22 aliases
    &FE20, the CRTC clock halves and the fields take twice as long. A NuLA takes it as its own
    reset.
- **virus.**
  - Clears: 38 `STA $pp00,X` (one a page), entered part-way by a self-modified BNE so that only
    the dirty height is cleared, 5.13 c a byte.
  - Objects: each edge is drawn once, via a 32-bit bitmap per object. Back faces are culled by a
    screen-space cross product.
  - raster.s keeps the error in X with a carry-set invariant. It has 8 steep and 16 shallow
    pixel-pair variants, writes `STA colour_both` when both pixels of a byte are lit, and chains
    edges with open end points so the next segment needs no new address.
- **beebgame's buffer select** sets ACCCON X with TSB/TRB, so it can't split an interrupt's write
  of D. The interrupt sets D in blanking (`src/engine/tiles.s`, `kernel.s`). With D=1, CRTC
  fetches below &3000 read HAZEL/ANDY (`defs.s`). An R12 write was lost on a real Master's VL6845
  when R4=0 ended a section (`kernel.s`).

### Kieran Connell

- [line-test](https://github.com/kieranhj/line-test) holds Elite-style, RTW (Rich's), NJ (Nick
  Jameson's) and Tricky's MODE 4S routines and a harness. We time all of them below.
- His [llm-beeb-wiki](https://kieranhj.github.io/llm-beeb-wiki/) page
  [techniques/bresenham-line](https://kieranhj.github.io/llm-beeb-wiki/techniques/bresenham-line)
  compares them by hand count: NJ ~26 c/px steep and ~5 c/px shallow pass-through, Tricky ~34,
  RTW ~42.
- Two of that page's claims don't hold:
  - It says Elite, RTW and Tricky draw both end points; they light max(|dx|,|dy|) pixels
    **[measured]**.
  - It says raster.s needs the 65C12; the default virus build passes `--cpu 6502` and assembles
    **[measured: ca65 --cpu 6502 here]**.
- The [port kit](https://github.com/kieranhj/beeb-port-kit) `docs/hardware-facts.md` §4 holds the
  Master shadow RAM, HAZEL and ANDY measurements cited below.

---

## 2. The Master 128's memory

**The map** **[source: [wiki memory/shadow-ram](https://kieranhj.github.io/llm-beeb-wiki/memory/shadow-ram),
[synthesis/model-differences](https://kieranhj.github.io/llm-beeb-wiki/synthesis/model-differences)]**:

| Block | Where | Size | Selected by |
|---|---|---|---|
| Main RAM | &0000-&7FFF | 32K | always |
| LYNNE (shadow) | &3000-&7FFF | 20K | ACCCON X (CPU), D (display) |
| HAZEL | &C000-&DFFF, over the MOS VDU code | 8K | ACCCON Y |
| ANDY | &8000-&8FFF, over the paged bank's first 4K | 4K | ROMSEL bit 7 |
| Sideways RAM | banks 4-7 at &8000-&BFFF | 4 × 16K | ROMSEL bits 0-3 (&FE30; the OS copy at &F4) |

**ACCCON, &FE34** (IRR TST IFJ ITU Y X E D):

- **D (bit 0):** the CRTC displays LYNNE.
- **X (bit 2):** every CPU access to &3000-&7FFF, opcode fetches included, goes to LYNNE.
- **E (bit 1):** data accesses go to LYNNE only for code running in the MOS VDU area &C000-&DFFF.
  - jsbeeb and b-em both turn E off when Y pages HAZEL in **[measured: jsbeeb
    `src/6502.js` writeAcccon; b-em `src/6502.c` write_acccon_master]**. So E only redirects the
    MOS ROM's own code, and game code in HAZEL can't use it to reach the shadow screen.
- **Y (bit 3):** pages HAZEL in.
- **The rule:** use X to draw into shadow RAM, D to show it, and never switch X from code in
  &3000-&7FFF **[source: wiki]**.
- D flips cleanly in the VSync handler **[source: port kit, jsbeeb]**. Switching D mid-frame
  worked in jsbeeb only; it's unchecked on b-em and hardware **[source: port kit]**.
- ACCCON (&FE34) and ROMSEL (&FE30) are 2MHz accesses: `STA` is 4 cycles, and TSB/TRB on &FE34
  is 6 **[measured: jsbeeb `src/6502.js:620`, &FE20-&FE3F not stretched]**.

**Free RAM once the game owns the machine** **[source: port kit §4 and §6, measured by Kieran in
jsbeeb]**:

- **Low RAM, about 10.7K:** &0400-&07BF (language workspace, once `*RUN` has handed over),
  &0800-&0CFF (sound, serial, soft keys and font, once the MOS interrupt is gone) and
  &0E00-&2FFF, leaving &0D00 for an NMI routine and &0D9F-&0DFF for the extended vectors a soft
  BREAK reads. Most of zero page is free too.
- **HAZEL:** all 8K if the game makes no more filing-system calls once HAZEL is loaded (BREAK
  must then be a power-on reset: `OSBYTE 200,3`). &C300-&DEFF (7K) stays usable with DFS OSFILE
  loads still working.
- **ANDY:** all 4K, if nothing calls `*KEY` or `VDU 23` or changes mode after it is filled; 3,328
  bytes otherwise.
- **Sideways RAM:** 64K, but only one 16K bank at &8000-&BFFF at a time. Code there runs at full
  speed. Paging is `LDA #n : STA &F4 : STA &FE30`, 9 cycles **[inferred]**.

So the RAM outside the screen area is about 10.7 + 8 + 4 + 64 = **86.7K**. About 22.7K of it is
never paged (low RAM, HAZEL, ANDY), and a 16K window is paged among four banks **[inferred]**.

**Double-buffering: what's left.** Two screens of S bytes take 2S of the 40K in &3000-&7FFF (main
plus LYNNE). The rest is free, but only through ACCCON X **[inferred]**:

| Screen (each buffer) | S | Left in &3000-&7FFF | Total for code and data |
|---|---|---|---|
| MODE 0, 1 or 2 full (640/320/160 × 256) | 20,480 | 0 | ~87K |
| MODE 1 256×256 (R1=64) | 16,384 | 2 × 4K | ~95K |
| MODE 1 256×192 (R1=64, R6=24) | 12,288 | 2 × 8K | ~103K |
| MODE 1 256×160, MODE 2 128×160, MODE 4 320×256 | 10,240 | 2 × 10K | ~107K |
| MODE 4 256×256 (R1=32) | 8,192 | 2 × 12K | ~111K |
| MODE 4 256×160 (R1=32, R6=20) | 5,120 | 2 × 15K | ~117K |

The screen's bytes are R1 × 8 × R6. A panel drawn into both buffers counts in S. A rupture split
can give a panel its own start address, but D still picks main or shadow for the whole frame
unless it's switched mid-frame, which is unchecked on hardware **[inferred]**.

**Two layouts:**

- **A. The same address in main and shadow (beebgame, Edge Grinder).**
  - Draw with X set to the hidden bank, show with D, and flip both in VSync: ACCCON EOR #&05.
  - Every drawing routine uses the same addresses for both buffers, so nothing is patched per
    buffer. Compare raster.s, which patches its overflow guards for each buffer in `set_page`.
  - The cost: whatever is left in &3000-&7FFF changes bank with X every frame. It suits identical
    copies of read-only code or tables (half the space, visible either way), or data read with an
    explicit X toggle.
  - Code there must never switch X **[inferred]**.
- **B. Both buffers in main RAM, flipped by R12/R13 (lander, virus, doom on a B).**
  - Needs 2S ≤ 20K. LYNNE's 20K is then one contiguous store, reached only with X set, for
    level data or sample data.
  - An interrupt that reads samples there must save, set and restore ACCCON, about 16 cycles
    **[inferred]**.
  - The same build runs on a B with 20K less **[inferred]**.

Either way, the hot drawing code and its tables belong in low RAM and HAZEL (never paged, and
never subject to X), and the game logic and shape data in sideways banks **[inferred]**. Real
hardware adds two traps:

- Nothing displayed may live below &3000. With D set, those CRTC fetches read HAZEL/ANDY in b-em,
  and jsbeeb disagrees **[source: port kit; beebgame `defs.s`]**.
- HAZEL taken means BREAK must clear memory **[source: port kit]**.

---

## 3. The Master's 65C12

The Master's CPU is a 65C12 at 2MHz: the 65C02 set without the Rockwell bit instructions. BBR, BBS,
RMB and SMB exist on the 6502 Second Processor and the Turbo, **not** on the Master itself
**[source: [wiki model-differences](https://kieranhj.github.io/llm-beeb-wiki/synthesis/model-differences)]**.
Timings below are from [wiki hardware/6502-isa](https://kieranhj.github.io/llm-beeb-wiki/hardware/6502-isa)
**[source]**.

| Instruction | Cycles | Use in a line or clear routine |
|---|---|---|
| `STZ abs,X` / `STZ abs` / `STZ zp` | 5 / 4 / 3 | Clears without tying up A. Our clears use `STZ abs,X` **[measured: 5.13 c/byte]** |
| `BRA` | 3 (4 across a page) | Out-of-line paths back into a loop. Relocatable, 2 bytes, and no carry or flag to rig as `CLC : BCC` needs |
| `JMP (abs,X)` | 6 | Jump tables per pixel position. Our MODE 1 routine enters its 16 blocks this way |
| `PHX` `PHY` / `PLX` `PLY` | 3 / 4 | Save X or Y in an interrupt: PHX is 3 c where TXA:PHA is 5, PLX 4 where PLA:TAX is 6 |
| `LDA (zp)`, `STA (zp)` | 5 | A pointer without Y = 0. Our sample player reads with `LDA (ptr)` |
| `TSB` / `TRB` abs | 6 | OR/AND-NOT a byte without loading it, but absolute only (no index), so for patched addresses and ACCCON bits |
| `INC A` / `DEC A` | 2 | Instead of `CLC : ADC #1` (4) |
| `BIT #imm`, `BIT abs,X` | 2, 4 | Tests without disturbing A |
| `ASL/LSR/ROL/ROR abs,X` | 6 (+1 across a page) | 7 on NMOS |
| `JMP (ind)` | 6 | 5 on NMOS (the page bug is fixed) |
| `ADC`/`SBC` in decimal mode | +1 | Keep D clear in inner loops |

**The 1MHz stretch.** Accesses to the following regions take 1 or 2 extra cycles, to meet the 1MHz
bus's phase **[measured: jsbeeb `src/6502.js:620-623, 1422-1423`]**:

- FRED and JIM (&FC00-&FDFF);
- the CRTC and ACIA (&FE00-&FE1F);
- both VIAs (&FE40-&FE7F);
- the ADC (&FEC0-&FEDF).

&FE20-&FE3F runs at 2MHz: the Video ULA, ROMSEL, ACCCON and the Master's 1770. So do &FE80-&FEBF
and the Tube at &FEE0-&FEFF. This matters for:

- R12/R13 flips (4 stretched writes);
- sound-chip writes (through the System VIA);
- timer reads.

It doesn't matter for screen RAM.

---

## 4. The cycle budget

### Line routines, timed

All measurements are **[measured]** by `tools/beeb_linebench.sh`:

- **Timing.** Each line is drawn alone, called from `SEI : JSR : JMP *` with interrupts off, and
  jsbeeb's cycle count is taken less the 14 cycles of the stub.
- **Check.** Each routine also passes a pixel check: 408 lines are drawn alone on a clear screen
  and read back, the right number of pixels must be lit, and each pixel must lie within a pixel of
  the true segment.
- **Line sets:**
  - *random*: 400 lines with end points anywhere in 256×160 (128×160 for MODE 2), averaging about
    100 pixels;
  - *short*: 400 edges of 4-40 px in random directions, averaging 20-21 pixels;
  - one-pixel lines (*point*);
  - fixed slopes of 96-144 px.
- **MODE 4S** is line-test's MODE 4 cut to 32 columns: 256 px wide with 256-byte rows. Elite's
  screen is the same.

| Routine (mode) | Plot | random c/px | short c/px | short c/line | point c | horiz | vert | diag | 1:2 | 2:1 |
|---|---|---|---|---|---|---|---|---|---|---|
| **Ours, NJ-style (MODE 1 256×160)** | EOR, 3 colours | **30.6** | **39.0** | **824** | 178 | 15.6 | 29.4 | 42.2 | 34.4 | 35.7 |
| NJ + Hamiltonian 1:2 (MODE 4S) | EOR | 26.5 | 39.1 | 826 | 271 | 11.8 | 30.1 | 35.7 | 30.5 | 35.4 |
| NJ (MODE 4S) | EOR | 28.6 | 40.5 | 856 | 258 | 11.7 | 30.1 | 45.1 | 30.4 | 35.4 |
| Tricky (MODE 4S) | EOR | 35.5 | 39.9 | 804 | draws 256 px | 31.3 | 35.5 | 39.3 | 35.2 | 37.7 |
| Elite Master LOIN (4-colour, shadow) | EOR, 3 colours | 39.7 | 50.5 | 1,017 | 131 (0 px) | 34.7 | 37.1 | 52.2 | 38.4 | 44.4 |
| Eben's raster.s (MODE 2 128×160) | AND/ORA | 45.9 | 49.5 | 985 | 104 (0 px) | 23.4 | 47.0 | 57.1 | 33.2 | 52.0 |
| Elite cassette LOIN (MODE 4S) | EOR | 45.9 | 58.7 | 1,183 | 365 (0 px) | 43.8 | 39.3 | 48.0 | 46.4 | 43.4 |
| RTW (MODE 4S) | EOR | 52.4 | 55.5 | 1,117 | hangs | 46.1 | 45.5 | 58.8 | 55.9 | 52.0 |

How to read the table:

- **What c/px counts.** It is cycles per lit pixel, so for open routines (Elite, RTW, Tricky,
  raster.s) it divides by one pixel fewer.
- **Placement.** Moving the MODE 4S binary by 8 bytes moved Elite's, RTW's and NJ's figures by
  up to 0.6%, from page-crossing branches and indexed reads. Treat the last digit as soft.
- **Wrappers.**
  - Elite cassette: 27 cycles a line of ours copy line-test's zero page into Elite's.
  - raster.s: our wrapper pays `init_base` on every line. Chained edges skip it.
- **Point.**
  - RTW hangs on a zero-length line. Tricky draws a full 256-pixel line for one.
  - Either needs a guard in a port.
- **"Ours"** is `tools/beeb_line_m1.py`: NJ's MODE 4 design moved to MODE 1, 2bpp in 256-wide,
  512-byte rows. It generates Baron source, 1,601 bytes as assembled with alignment.
  - One unrolled block per pixel position, with dx and dy patched into each block.
  - The error lives in A with the carry kept set.
  - Shallow runs build up a byte's mask in X and are written with one EOR a byte-row.
  - Only minor-axis steps are counted, with NJ's lowered-error trick for the last run.
  - Colours 1-3 are patched in once per colour change. It uses `JMP (abs,X)` and `BRA`.
  - **It matches the best MODE 4 routines per edge.**
- **The per-pixel floor** is the plot itself: `LDA #m : EOR (scr),Y : STA (scr),Y`, 13 c. Steep
  lines add ~13 c of error, row step and loop.
  - In MODE 1, shallow lines do 5 c a pixel between y-steps plus one read-modify-write per
    byte-row run (4 px a byte, against MODE 4's 8). Hence 15.6 against 11.7 horizontally.

**Short edges are set-up-bound.** Ours spends ~178 cycles before its first pixel, then ~32 c a
pixel on a 21-pixel edge: (824 − 178) / 20.1 **[inferred]**. A scene of 100 short edges spends
~18K cycles on set-up alone. The ways to cut that **[inferred]**:

- Fewer patched operands: zero-page dx/dy cost a cycle a pixel each but save the patches.
- Edge chaining with open end points (raster.s), which keeps the screen address from the previous
  edge.
- Drawing each shared edge once (virus's per-object bitmap).

### Erase

Erase costs, all **[measured]** unless tagged:

| Method | Cost |
|---|---|
| Full clear, `STZ abs,X` per page, `INX : BNE` | 10K (MODE 1/2 256/128×160): **52,481 c**; 5K (MODE 4 256×160): 26,881 c; 20K: 104,192 c. 5.09-5.25 c a byte |
| EOR redraw of the lines drawn into this buffer two frames ago | the cost of drawing them: 39.0 c/px on short edges in MODE 1 |
| Clear only the dirty region (virus: dirty height; lander: per-column top and bottom) | 5.1 c a byte of that region, plus set-up **[inferred]** |
| Zero along the old lines a byte at a time (`STA (scr),Y` with A = 0, at byte resolution) | ~4× fewer writes than pixels on shallow lines in MODE 1, the same count on steep ones; not built **[inferred]** |

A full 6502 clear can't go below 4 c a byte (fully unrolled `STA abs`, 3 bytes of code per byte
cleared), and 5 c with `abs,X`. At 5.13 c a byte, a 10K view costs 1.31 fields just to clear
**[measured]**.

With double buffering, EOR erase needs a line list per buffer: the lines drawn there two frames
earlier. Erasing in the same buffer, as Elite does, can be made flicker-free one line at a time
(Master Elite's LSPUT) **[source]**.

### Pixels a frame (view 256×160)

These figures give all the CPU to lines and erase, with nothing for maths, game logic or sound. The
short-edge cost is used (an average edge of 21 px), and every count is **[inferred]**:

| Mode, erase | 25fps (79,872 c) | 16.7fps (119,808 c) |
|---|---|---|
| MODE 1, EOR redraw (2 × 39.0 c/px) | 1,024 px, ~49 edges | 1,536 px, ~73 edges |
| MODE 1, full 10K clear (52,481 + 39.0 c/px) | 702 px, ~33 edges | 1,726 px, ~82 edges |
| MODE 4, EOR redraw (2 × 39.1) | 1,021 px | 1,532 px |
| MODE 4, full 5K clear (26,881 + 39.1) | 1,355 px | 2,377 px |
| MODE 2 128×160 (raster.s), full 10K clear (52,481 + 49.5) | 553 px | 1,360 px |

With **half** the frame left for 3D maths and game logic:

- **MODE 1 EOR:** 512 px (24 edges) at 25fps and 768 px (37 edges) at 16.7fps.
- **MODE 1 with a full clear:** impossible at 25fps (52,481 > 39,936), and 190 px at 16.7fps.
- **MODE 4 with a 5K clear:** 334 px at 25fps and 845 px at 16.7fps.
- **An 8kHz sample player** (34.3% measured) scales every figure by 0.66.

On long lines (30.6 c/px in MODE 1, 26.5 in MODE 4) the budgets grow by about a quarter (MODE 1:
39.0 / 30.6) to a half (MODE 4: 39.1 / 26.5).

**The crossover.** EOR redraw beats a full 10K clear in MODE 1 below 52,481 / 39.0 ≈ **1,350
pixels a frame**. A 5K MODE 4 clear breaks even at 26,881 / 39.1 ≈ 690. EOR redraw is also the
only erase whose cost falls with the scene, and it keeps the see-through wireframe: crossings
cancel under EOR, the price of drawing in EOR at all **[inferred]**.

---

## 5. Sampled sound on the SN76489

**The technique** **[source:
[scarybeasts 2020](https://scarybeastsecurity.blogspot.com/2020/06/sampled-sound-1980s-style-from-sn76489.html),
[smspower SN76489](https://www.smspower.org/Development/SN76489)]**:

- **Carrier.** Set a tone channel's period to 1 and write its 4-bit attenuation at the sample
  rate. On the BBC, period 1 is a 125kHz square wave, not DC; the analogue stage filters it, so
  the volume steps come out as the signal (at half amplitude).
- **Period 0.** It means 1024 on TI chips. jsbeeb, b2 and beebjit treat 0 as 1024, and b-em gives
  DC for any period up to 4 **[measured: emulator sources]**. Every BBC player read uses period 1.
- **Volume steps.** Attenuation k is −2k dB, linear 10^(−k/10), with 15 meaning off. That is a
  4-bit logarithmic DAC.
  - One channel is ~2.6 bits linear-equivalent over 28dB, which suits speech better than the
    figure suggests.
  - Summing channels gives ~4.9 bits from two and ~5.9 from three, at 2-3 chip writes a sample
    **[inferred, agent's script]**.

**Writing the chip.**
- The System VIA's port A goes to the chip, latched by line 0 of the addressable latch.
- Per byte: `STA &FE4F` (not &FE41, which clears CA1/CA2), `STZ &FE40` (/WE low), at least ~12-16
  cycles, then `LDA #8 : STA &FE40`.
- The keyboard must be on auto-scan (&0B to &FE40) **[source: TI datasheet via
  [nouspikel](https://unige.ch/medecine/nouspikel/ti99/tms9919.htm);
  [sampstream.asm](https://github.com/scarybeasts/misc/blob/master/sampstream/sampstream.asm):
  6µs works and 5µs fails on an issue 3 B]**.
- Each VIA access is 1MHz-stretched **[measured: jsbeeb]**.

**The cost, measured.** `tools/beeb_soundbench.mjs` runs a foreground counting loop for one
emulated second, with and without a User VIA T1 free-running interrupt that plays samples. The
handler:
1. tests its source (`BIT &FE6D : BVC`);
2. acknowledges T1;
3. reads `(ptr)`;
4. writes the chip with a 16-cycle /WE hold that does the pointer bump;
5. returns through the MOS's IRQ entry. Any game pays that entry: the vector at &FFFE is in ROM
   (&E59E: `STA &FC : PLA : PHA : AND #&10 : BNE : JMP (&204)`).

All figures **[measured]**:

| Rate | Acknowledge only | One latch byte a sample | Two 4-bit samples a byte |
|---|---|---|---|
| 4.0kHz | 9.9% (49.5 c an IRQ) | **17.2%** (85.8 c), 6,864 c a field | 21.0% (104.8 c) |
| 6.0kHz | 14.9% | **25.8%**, 10,313 c a field | 31.6% |
| 8.0kHz | 20.0% | **34.3%**, 13,728 c a field | 41.8% |
| 11.0kHz | 27.4% | **47.3%**, 18,903 c a field | 57.5% |

- **The floor.** Half the cost (~50 c) is the IRQ itself, the MOS entry, the acknowledge and the
  RTI, so no handler gets much below ~50 c a sample **[measured]**.
- **Samples in sideways RAM** add a ROMSEL save, set and restore if the foreground pages too
  (~+20 c). Samples in LYNNE add an ACCCON save, set and restore (~+16 c) **[inferred]**.
- **Jitter.** IRQ latency of a few cycles is ~3% of an 8kHz period and inaudible, but any SEI
  section longer than a sample period (250 c at 8kHz) delays a sample. Music or effects writing
  two-byte tones must SEI across the pair **[source: sound agent's read; `../porting-to-the-beeb.md`]**.
- **A tight loop** without interrupts writes every ~32 cycles and can mix 3-4 voices at 12.5-15kHz
  (scarybeasts' [beebmod](https://github.com/scarybeasts/misc/tree/master/beebmod)). It takes the
  whole CPU: a title screen only **[source]**.

**Prior art:**

- **Superior's Speech!** (David Hoskins) is a phoneme synthesiser from recorded 128-sample
  waveforms, with interrupts off while it speaks (used in Citadel and Repton 2) **[source:
  [nvg](https://oldwww.nvg.ntnu.no/bbc/doc/Speech.html)]**. Acorn's Speech Upgrade is a TMS5220,
  not the SN, and the Master has no speech socket **[source: wiki model-differences]**.
- **Exile, the sideways-RAM/Master version, speaks during play.** It has seven phrases, 5.4 s in
  3,992 bytes (~740 bytes/s). Its 1-bit run-length scheme takes one T1 one-shot interrupt a run,
  ~1,400 a second **[measured: level7 disassembly, sound agent]**.
- **3D Pool** (Firebird 1989) plays 4-bit packed ball sounds of 91-215 bytes during play, from
  System VIA T1 at 4.95kHz **[measured: level7 disassembly, sound agent]**.
- **Bonecruncher's loader** plays its speech at 7kHz, on the title only. It loops 14-byte sections,
  ~390 bytes/s, about 9:1 against 4-bit PCM **[measured: level7 disassembly, sound agent]**.
- **sampstream** streams 6.5kHz 4-bit audio from disc (400K) **[source: scarybeasts]**.

**Memory**, 4 bits a sample, packed two a byte (unpacked is double) **[inferred]**:

| Rate | 15 s song | 3 s speech | Song as sideways banks |
|---|---|---|---|
| 4kHz | 30,000 | 6,000 | 1.8 |
| 6kHz | 45,000 | 9,000 | 2.7 |
| 8kHz | 60,000 | 12,000 | 3.7 |
| 11kHz | 82,688 | 16,538 | 5.0 |

What this means for the port **[inferred]**:

- **The title song.** 8kHz needs nearly all four sideways banks, so it can only be title-time
  data: loaded for the title, then overwritten by the game's data, or streamed from disc as
  sampstream does at 6.5kHz.
- **Smaller encodings.** 2-bit ADPCM halves those figures. Exile-style 1-bit run lengths fit
  speech in ~0.75K a second (voice quality, not music).
- **Speech in play.** At 6kHz packed, speech costs ~32% of the CPU while it plays, which would
  take 25fps to ~17fps for the length of a phrase, and ~9K for 3 s.
- **Cheaper choices.** Exile's run-length scheme, or speaking at moments when the frame has room.

The **Spectrum 128** has a cheaper DAC. With tone and noise off, an AY channel's volume register
is the output level directly, one `OUT` a sample, in ~3dB steps **[source:
[cpcwiki PSG](https://cpcwiki.eu/index.php/PSG)]**. Starglider 128's "AY Speech" is listed at
[Spectrum Computing](https://spectrumcomputing.co.uk/alt/4863/ZX-Spectrum/Starglider) **[source]**.

---

## 6. Optional hardware

**VideoNuLA** (Rob Coleman) is a drop-in Video ULA replacement **[source:
[wiki hardware/video-ula](https://kieranhj.github.io/llm-beeb-wiki/hardware/video-ula)]**.
- **What it adds:** a 12-bit palette (16 colours from 4096), pixel-by-pixel horizontal hardware
  scroll, and attribute modes.
- **Programming.** Palette entries go to &FE23 as two bytes, `[index<<4 | R]` then `[G<<4 | B]`.
  &FE22 = &40 resets it and &11 selects logical mapping **[source: port kit §2, measured on
  hardware by Kieran]**.
- **Detection.** Its registers can't be read back, so lander detects it by timing the CRTC clock
  through the &FE22/&FE20 alias (§1) **[measured: source]**.
- **jsbeeb** emulates the palette but not the scrolling or attribute modes **[source: wiki]**.
- **For a wireframe game** the gain is choosing MODE 1's four colours, or MODE 2's sixteen, from
  4096. A NuLA variant costs one palette table and the detection, and changes no drawing code
  **[inferred]**. Edge Grinder and lander both ship NuLA builds **[source]**.

**The 6502 Second Processor**, external at 3MHz, or the Master's internal 65C102 Turbo at 4MHz
**[source: wiki model-differences]**.
- **What Elite does with it.** The co-processor does the maths, and the BBC still draws every
  line. Lines cross the Tube in batches and drawing overlaps the next frame's maths, for "~20%"
  **[source: §1]**.
- **For Starglider** a Tube variant takes the 3D transform, clipping and game logic off the host,
  but not the drawing or the erase, which set the budgets above **[inferred]**.
  - Receiving a line's four bytes through the Tube's 2MHz registers costs the host perhaps
    40-60 cycles. That is under 10% of an ~800-cycle edge.
  - So the variant pays only if the ST's maths takes a large share of the frame once ported, at
    least ~30%. The ST and 6502 research will say.
- **jsbeeb** emulates a Tube co-processor (its `src/6502.js` runs `this.tube.execute` each
  poll), so such a variant could be measured the same way **[measured: source]**.

---

## Tools

| File | What it does |
|---|---|
| `tools/beeb_linebench.sh WORKDIR` | Clones kieranhj/line-test (969dfd3), markmoxon/elite-source-code-bbc-master (b892ec6) and ebenupton/virus (468719e) into WORKDIR, builds every routine and runs the bench. Needs `BEEBASM` (a source build: the snap can't read /tmp), `CC65BIN` (ca65/ld65), baron and node |
| `tools/beeb_linebench.mjs WORKDIR` | Times and checks each routine on jsbeeb's Master headless and writes `WORKDIR/linebench.json` |
| `tools/beeb_linebench_m4.asm` | beebasm wrapper for line-test's routines and Elite's cassette LOIN (transcribed instruction for instruction) |
| `tools/beeb_line_m1.py` | Generates our MODE 1 line routine as Baron source |
| `tools/beeb_soundbench.6502`, `tools/beeb_soundbench.mjs WORKDIR` | The sample-player interrupt and the clears, built in variants by Baron and timed in jsbeeb |

## Caveats

- **Hardware.** Everything measured ran in jsbeeb, not on hardware. The figures are cycle counts
  of deterministic code, so the remaining risk is jsbeeb's 1MHz-stretch model (it matters for the
  sound figures only) and the ACCCON behaviours the port kit flags as unchecked on hardware.
- **Scene size.** The pixel budgets depend on how many edges a Starglider frame has and how long
  they are. The ST research should count them per frame, so these budgets can be turned into a
  frame rate.
- **Subagent reads.** The figures that subagents read from code (boom, doom, lander, virus,
  Aviator, Revs, Exile, 3D Pool and Bonecruncher) carry file references, but we didn't
  re-derive them.
