# Starglider on the Atari ST: the cockpit panel

*Everything the ST draws on its cockpit picture and in the view besides the
3D: the panel's gauges, scanner and numbers, the gunsight, the messages and
colour 0's flashes, read from the disassembly (`build/st/star.s`) and
checked in Hatari on 2026-10-18, for the port to draw the panel from. Tags:
**[code]** read from the disassembly; **[measured]** checked in a Hatari
screenshot. Addresses are text-segment offsets; `$nnn(a6)` the variable
block, as in `st.md`.*

## Conventions

- **Screen offsets.** For a colour screen offset `o`: y = o div 160, b = o
  mod 160, x = 16·(b div 8) + (8 if b is odd).
- **Palette** (flight, RESULT.TRA): 0 000, 1 700 red, 2 070 green, 3 760
  yellow, 4 730 orange, 5 737 magenta, 6 077 cyan, 7 056, 8 034, 9 014, 10
  003, 11 066, 12 045, 13 024, 14 002, 15 777 white.
- **Text** goes through print_at_a0 &0112E → &01264 / &01424.
  - The font is font_colour &16D88: 8 bytes a glyph from char &20, row 0 at
    the top, MSB on the left. &20-&7A are populated; &5B-&60 and &7B up
    are blank; the block is 864 bytes.
  - Each character overwrites a whole 8×8 cell in all four planes: glyph
    pixels take the colour in &019F0, the rest become colour 0. Cells are
    opaque.
  - The cursor advances 8 px. A byte ≥&80 sets the colour to its low 7
    bits, &0A moves down 8 rows, &0D is ignored, NUL ends the string.
  - Strings without a colour byte print in whatever colour the last print
    left.
- **The static picture.** Game start (&039B2) copies RESULT.TRA to both
  buffers (&70000, &78000), clears the window, and fades the palette in
  (&06ACC). Nothing else ever restores the picture: the panel only rewrites
  the regions listed here; everything else is static.
- **When the panel is redrawn.** "The panel" is the one routine `waveforms`
  &05872-&05FEE (the mono copy is &062A6-&06ACA). It redraws every element
  every time it runs, with no change test. It runs every normal-view frame,
  including the tunnel, docked and launching (&05166); every missile-view
  frame (&054AC); every Interrogate frame (&02B3E). It doesn't run on the
  level-change flash, the title or game over.

## 1. The top bar (rows 0-7; the picture has empty black boxes at x 32-95, 138-182 and 224-287)

- **Score.** &0150C, 8 BCD digits with leading zeros, colour 3, cells at
  (32,0), x 32-95. Printed by &00D8E: base 0(a6)+$128 (&10); &019F0 is set
  to 3 at &05092. Normal-view frames only, after adding $D4 [measured].
- **Last kill.** $286, the BCD word printed as 4 digits with leading zeros
  by &04A82, colour 4, at (240,0), x 240-271. Base &05060 + $12A (&78).
  Printed before $286 is updated from $D4, so it is one frame late.
  Normal-view frames only [measured].
- **Top centre: the heading, red digits and a green letter** (&05F38-&05FC4).
  - deg = ((($13C & &FFF) << 5) divs 365) & &1FF, which gives 0..359 (not
    exactly ×360/4096).
  - &04598 formats it in decimal, left-aligned, without leading zeros. The
    NUL becomes a space and the field is padded with spaces to 4 cells.
  - Then &82 switches to colour 2 and the compass letter follows: N if deg
    ≥ 315 or deg < 45; E for 45-134; S for 135-224; W for 225-314.
  - The digits are colour 1 at (144,0), x 144-175; the letter is colour 2
    at (176,0). The letter's cell overwrites the frame pixel at x 183.
  - Shown as "0   N" at the start [measured].

## 2. The gauges (&05A4A-&05C45; the bank ticks are &05C46 on)

**Bars.** Shields $260, energy $25E, laser energy $28A (unsigned, &FFFF
full).

- Each bar is 32×4 px, cleared to colour 0 every frame.
- If v = 0 there is no bar. Otherwise i = v>>11 (0..31) and the length is
  i+1 px from the left. The patterns are the table D_06026 (64 words): left
  group T[i], right group T[i+32].
- The bar is written to planes 0 and 2, so it is colour 5.

| Bar | Area | Note |
|---|---|---|
| Shields | x 48-79, y 145-148 (&5AB8) | in the picture's box x 43-80 |
| Energy | x 240-271, y 145-148 (&5B18) | blinks when i < 6 (v < &3000) |
| Laser | x 48-79, y 154-157 (&6058) | erases the box edge pixel at x 78 |

- **Energy blink.** a0 += $27E, which moves the bar to planes 1 and 3,
  colour 10 (003). $27E (set to 2 at &03ACA) is XORed with 2 on frames
  where ($1E2 & 2) = 0 (&0597E), so it is 0 one frame in four and 2 on the
  other three, or the reverse: the phase depends on $1E2's history.
- **Measured** with shields &8000, laser &4000 and energy about &1F38: 17
  px, 9 px and 4 px.

**Altitude** (left vertical, x 38-41, &05994).

- d0 = ((−$130) asr 6) & 31, so 0..28.
- Clear: all planes, rows 198 up to 170 (29 rows).
- Draw: d0 rows from 198 upward in colour 1 (red), then the remaining
  28−d0 rows up to row 171 in colour 2 (green).
- Low-altitude blink: if d0 < 8 and ($1E2 & 4) = 0, the green part is
  colour 6 (cyan).
- Row 170 stays black, which cuts a notch in the picture's colour-10
  border.
- Measured: y = −1000 gives 15 red rows (184-198) and 13 green; at y near
  −20 it is all green, with the notch.

**Speed** (right vertical, x 278-281, &05A14).

- d0 = ($21E >> 4) & 31, so 0..29.
- Only plane 1 is touched: OR for d0 rows from row 198 upward, then
  cleared for the 31−d0 rows above, up to row 168.
- The result on the picture: rows 171-198 colour 2 where lit, 0 otherwise;
  row 170 10 if lit (d0 = 29), otherwise 8; row 169 always 5, a magenta
  notch on a blue border; row 168 always 8.
- Measured at speed 20 and speed 400 (25 rows); the notch shows in
  hatari_flight.png.

**Bank ticks** (&05C46-&05DB0).

- d = (($13E asr 1) + 16) & 31. It wraps if roll plus the jolt passes ±32.
- Clear planes 0 and 2 in two areas, rows 170-173: x 80-113 and x 206-239.
- Then plot colour 1 dots with sub_09768, d3 = &800 (dots 1 px wide and 2
  rows high, at y 170 and 172): (82+d, 170-173) and (206+d, 170-173).
- Each tick is 1×4 px, centred at x 98 and 222 when roll is 0. The boxes'
  green borders (x 81/115 and 205/239) are untouched.
- Measured: acc &100 put the ticks at 90 and 214.

## 3. The scanner (&05DB2-&05EA4)

- Clear x 144-175, y 148-180 to colour 0 except (160,164), which is colour
  15 (the player). This also wipes the picture's centre line at y 164
  inside that span.
- Then, for each near-list entry (list $98, count $240, built this frame by
  &057B8): camera-space x = +28 and z = +2C (the camera matrix includes
  pitch and roll). Accept only if −&2000 < x < &2000 and −&2000 < z <
  &2000 (strict). Pixel: px = 160 + (x asr 9), py = 164 + ((−z) asr 9);
  ahead is up. Colour: D_06006[type] (byte table &06006), ORed into the
  colour's planes.
- Which objects can appear: the near list is the coarse list (&05750)
  without exploding (+24) or free objects. The coarse test is
  world-aligned, so corners of the rotated square can be missing.

| Type | Colour | | Type | Colour |
|---|---|---|---|---|
| 0 | 0 | | 16 | 11 |
| 1 | 7 | | 17 | 12 |
| 2 | 3 | | 18 | 13 |
| 3 | 1 | | 19 | 14 |
| 4 | 7 | | 20 | 5 |
| 5 | 5 | | 21 | 6 |
| 6 | 13 | | 22 | 15 |
| 7 | 6 | | 23 | 15 |
| 8 | 13 | | 24 | 1 |
| 9 | 15 | | 25 | 15 |
| 10 | 7 | | 26 | 15 |
| 11 | cycles | | 27 | 4 |
| 12 | 1 | | 28-31 | 0 (invisible) |
| 13 | 5 | | | |
| 14 | 3 | | | |
| 15 | 8 | | | |

- Type 11 (&06011) is rewritten every frame by animate_shapes (&04508)
  with the beam colour: +1 & 15, so it includes 0.
- Docked: the list is the tunnel (22, white) and the silo's missile (24,
  red). Missile view: built around the missile only once the window is
  open ($27C = 0); stale while it opens or closes. Interrogate: stale from
  the last docked frame.

## 4. The bottom numbers

- **Sector X.** ((u16)$12E / &290) & &FF → 2 digits with a leading zero,
  colour 4, at (144,190) (&7708).
- **Sector Z.** The same from $132, colour 3, at (160,190) (&7710). They
  fill the picture's box x 144-175 exactly and overwrite its "08-06".
  Measured "5050".
- **Missiles.** ($278 & 15) + '0', colour 4, at (64,191) (&7780). The
  value is 0-2: 1 at the start, 0 after L [measured].

## 5. The waveforms (decoration)

- Two 16×8 blits, overwriting all planes: left at (96,155) (&6110) with
  counter $266; right at (208,155) (&6148) with counter $268. Each counter
  = (counter + 1) & 15 per panel call; both are cleared at &03ABE.
- 16 frames of 64 bytes at &06E2A + 64k, colour 3 only. The pattern is a
  sine about 16 px long, 7 rows high, with row 7 blank. Frame k is frame 0
  scrolled k px left, but frame 15 is a byte copy of frame 14.
- Left uses pointer table &06D2A: frames 0..15 (one pixel left per frame;
  it stalls at 14→15). Right uses &06D6A: frames 15, 13, 11, 9, 7, 5, 3, 1,
  then repeats, so it runs right about 2 px a frame.
- They advance once per rendered frame, not per VBL.

## 6. The gunsight (world_render &050EE → &05598 → blit_colour &09842)

- **Bitmap.** D_0732A: header (8 words wide, 16 rows, hotspot 14,8), then
  16 rows × 2 groups × 4 planes. All planes are equal, so it is colour 15.
- **Pixels, for a sight at (sx,sy):** horizontal strokes x sx−6..sx−2 and
  sx+4..sx+8 on rows sy−8 and sy+7; vertical strokes x sx−6 and sx+8 on
  rows sy−7..sy−4 and sy+3..sy+6; centre dot at (sx+1, sy). Measured at
  (160,68).
- **Position**, set by place_sight &079BC: sx = 160 + (&01842 asr 2), range
  36..284; sy = 68 + ((−&01844) asr 3), range about 28..108; F (fixed
  sight) → (160,68).
- Drawn only if $146 ≤ sx < $148 and $14A ≤ sy < $14C, which always holds.
- The blit writes a 32-px box (48 px when not word-aligned) × 16 rows with
  no mask, onto the freshly cleared window and before the dots and
  objects, which OR over it. Normal-view frames only.

## 7. The messages

| Text (exact) | Cell | Colour | Shown when |
|---|---|---|---|
| `DOCKING, PRESS I FOR INTERROGATE` | (32,120) | 15 | docked and $292 ≠ &1E; every frame; before the 3D, so lines OR over it (&05002) |
| `Lasers and Shields replenished.  ` | (32,100) | current, 4 [measured] | $292 = &1E, every frame (main loop &01FD4); printed on the **shown** buffer after frame_end |
| `  Press SPACE BAR to launch,     ` | (32,110) | same | same |
| ` or I to Interrogate computer.   ` | (32,120) | same | same |
| `LAUNCHING FROM SILO` | (80,120) | 15 | 29 frames, $292 = &1D..1 (&0562E), before the 3D |
| `ENERGY CELLS REFUELLING` | (64,120) | 15 | $2C3 set (&05188); after the 3D; one frame behind the &500 flash |
| `WARNING:  MINE DETECTED` | (64,120) | current (4, or 15 after the refuel text) | mine handler &07B9A: mine in the draw list, &600 ≤ cam z < &800, $298 = 0, not docked, not missile view |
| `MINE HAS JUST EXPLODED!` | (64,120) | current | the single frame it explodes (−&800 ≤ z < &600, &07B44); colour 0 = &333 |
| `    LEVEL   ` + level in decimal | (96,120) | current, 4 [measured] | level_message &0260C: $298 frames (50 at a new game and each level change), not counted in the missile view |
| `YOU NOW HAVE MANUAL CONTROL!` | (48,50) | same | together with LEVEL [measured] |
| `MISSILE VIEW` | (96,120) | 15 | opening frames with $27C ≥ &11 after the step (12 frames) [measured] |
| the missile's countdown | (96,24) | 4 | below [measured "206"] |
| `   POWER DRAINAGE TOO GREAT!` / `SHIELD DEPLETED,  AGAV DESTROYED!` | (32,100), shown buffer | current | game over (&02160); then colour 0 = 0 |

- Text inside the view is erased by the next clear of that buffer, or by
  the picture copy in the missile view.
- **The missile's countdown.** $276−&F in decimal without leading zeros
  (D_06002), printed only when the window is open. When $276 < &38 it is
  shown only on frames where ($1E2 & 4) = 0.
- **Interrogate:** `Press E to exit, SPACE to continue` at (24,12) colour
  1; the name at (56,22) colour 3; two description lines at (24,104) and
  (24,114) colour 2. The strings carry their own colour bytes.

## 8. The missile view (L_05248)

- **The picture slides** (&06B7E, every frame). Screen rows 10..130−$27C,
  x 16-303, take picture rows (10+$27C).. onward; rows 131−$27C..130 are
  filled with 0. $27C goes &70→0 by 8 a frame: 14 frames of the picture
  sliding down. It closes the same way when $276 < &F.
- **3D.** Drawn only when $27C = 0, clipped to x 80-239, y 16-(112−$27C).
- **The bar** (open only). 17−n blocks, n = (($276−&F) asr 4) & 15
  (st-logic.md says 16−n; the dbra makes it 17−n). Each block is 4×4 at
  x_k−2..x_k+1, y 118-121, colour 7, ORed over the picture's yellow pips
  (colour 3 → 7). x_0 = 211; each next block is 6 px left, with 2 px extra
  before blocks 8 and 9: 211, 205, …, 169, 161, 153, 147, …, 111. Measured:
  5 blocks at a countdown of 206.
- **Side effect.** Row 130 (x 16-303) is black in both buffers after the
  first missile view, for the rest of the game [measured].

## 9. Colour 0 and the palette

- The panel itself changes no palette entries.
- $242 is written to colour 0 at frame_end (&08ECA) and then cleared, so a
  flash lasts one rendered frame and recolours every colour-0 pixel, panel
  boxes and text backgrounds included.

| Value | Cause | Address |
|---|---|---|
| &020 | enemy hit | &07EC6 |
| &333 | mine | &07B8E |
| &222 | laser kill | &087DA |
| &555 | ram (shows a frame later) | &020BA |
| &036 | every docked frame | &05026 |
| &040 | missile pick-up | &05720 |
| &500 | every refuelling frame | &0852A |
| random32's low word | each of the 29 launch frames | &0565A |

- Interrogate frames end up on 0.
- **The level change** (&026B2): fill the window with colour 15 and show
  it; strobe colour 15 with `not.w` 65,536 times; set colour 15 to &555
  and fade it by &111 a VBL; restore colour 15. All colour-15 panel pixels
  flash with it.

## Corrections to the other research files

- st-logic.md swaps the colour and mono offsets: the refuel text is &4B20
  in colour (64,120), and the countdown is &F30 (96,24), not &F18.
- st.md's scanner y is 164 + floor(−z/512), with strict ±&2000 limits in
  camera space.
- The gauges start at &05A4A, not &05C46.
- st.md's open question on the top centre is settled: shields top-left,
  energy top-right, laser lower-left, altitude left column, speed right
  column, and the top-centre readout is the heading and its compass point.

## Not settled

- **The mine messages' and game over's text colour.** Inferred to be the
  last print's colour, normally 4; the same mechanism measured 4 for LEVEL
  and the docked menu. To confirm, teleport next to a mine in Hatari and
  take a screenshot.
- **The energy blink's phase** depends on $1E2 at the game's start and on
  level changes.
