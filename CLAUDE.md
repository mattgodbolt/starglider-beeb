# STARGLIDER (BBC Master 128 port) — notes for Claude Code

A port of Argonaut Software's *Starglider* (Rainbird, 1986) to the BBC
Master 128, with Argonaut's blessing. Run the way the Chuckie Egg 2 and
Ninja Massacre ports were
(`../chuckie-egg-2-beeb`, `../nm`), from `../porting-to-the-beeb.md`;
their tools and docs are the model.

- `docs/brief.md`: the brief the port starts from: every version of the
  original, how it works, and the decisions to make first.
- `docs/plan.md`: the plan after the speed spike: what the rest of the
  game costs in time and memory, the memory map and the frame, the order
  of work.
- `docs/journal.md`: how it got here, in order. Add to it as you go.
- `docs/research/*.md`: the reverse engineering, one file per version;
  `st-logic.md` is the ST's game logic, inventoried for transcription;
  `st-panel.md` everything the ST draws besides the 3D (the panel, the
  gunsight, the messages).
- `docs/decisions.md`: every call the port makes that the original
  didn't, numbered, with the reason. Nothing changes quietly.

## The rules (from kieranhj/beeb-port-kit)

1. **The original is the specification.** Find what it does and
   transcribe its tables, constants and logic. When the BBC forces a
   change, port the original's *decision*, not just its effect.
2. **Deviations are numbered decisions** in `docs/decisions.md`. Matt
   makes the design calls: lay out the options with figures.
3. **One layer at a time**, working and visible in the emulator before the
   next starts.
4. **Measure, don't recall.** Run it, read the bytes, read memory back.

The ethos is the original's: fast, smooth wireframe vectors, one colour
an object. The ST culls each object's back faces but never lets one
object hide another, and the manual makes that part of the fiction (the
AGAV's "Enhanced Vision System" shows "a stunning translucent display of
anything within its visual range, even if objects are behind solid
buildings").

## Commands

```sh
make            # build/starglider.ssd (src/main.6502) and the speed
                # spike's build, build/spike (src/spike.6502)
make run        # boot the disc in jsbeeb, screenshot to shots/run.png
make disc       # the disc from a clean tree, as starglider.ssd: the
                # README links it (github: in jsbeeb's URL, not gh:)
make spike      # the spike on every captured scene: checked against the
                # ST's renderer, and timed (tools/scenecheck.py)
make check      # sincos against the ST's sine table at every angle, make spike, the
                # disc's erasing (tools/erasecheck.mjs), its own disc reader
                # (tools/disccheck.mjs), its controls (tools/inputcheck.mjs),
                # its front end's flows (tools/frontcheck.mjs),
                # make panel, make view and make rot (the rotations against
                # the ST's exact one and the approximation's model)
make logic      # the port's game logic against the ST's, routine by routine
                # and a whole step (tools/logicrun.mjs, on the captures make
                # steps makes)
make panel      # the panel drawn from those captures' frames, every pixel
                # against a model of the ST's formulas (tools/panelcheck.mjs;
                # --png DIR --at CAPTURE:FRAME renders, --colours an option)
make view       # the view besides the objects (the gunsight, the ground dots,
                # the bolt, the shots, the missile view's window) against the
                # ST's on those captures, and the shots against the scenes'
                # own lines (tools/viewrun.mjs)
make sfx        # the sound effects on the disc against the ST's YM writes,
                # converted (in make check; tools/sfxcheck.mjs)
make sfxcapture # capture the ST's effects in Hatari (slow; build/sfx/all)
make song       # the title song's two candidates as the SN76489 would play
                # them, WAVs in build/song (docs/research/song.md)
make tune       # the disc's title song against the Spectrum 128K's AY
                # registers and mksong.py's zx_bass model, every tick of a
                # pass and into the loop, its bass's edges timed, and its
                # render against the model's (in make check;
                # tools/songcheck.mjs, tools/songcompare.py)
make soak       # the whole disc played by a random player, a seed a process
                # (tools/soak.mjs; SOAK_SEEDS, SOAK_SECS, SOAK_JOBS): the PC,
                # every write, the stack, the interrupts, the logic's state,
                # the erase, each new game's start against the first's; a
                # short one is in make check
make memory     # what each region of the memory map holds (src/memory.6502)
make fps        # the disc's frames and steps a second
make scenes     # capture the scenes in Hatari (slow; needs ../hatari)
make fetch      # download every version into original/ (not committed)
make venv       # .venv (uv sync): SkoolKit, Capstone, Pillow, NumPy
```

The build makes the shapes and per-type tables from the ST's STAR.PRG
(`tools/mkshapes.py`), and the object handlers' tables (the handler by
type, the arctan tables, the missiles' by type and level:
`tools/mkhandlers.py`), and generates the line drawer, the camera rotation
and the vertex transforms (`tools/mkline.py`, `mkrotate.py`,
`mkxform.py`) into `build/gen/`; baron computes the sine table
(`src/sine.6502`) and the multiply and reciprocal tables.
`tools/mkobjects.py` lays out the object table (decision 13: an array a
field, by slot) and writes `build/gen/objects.json`, which the harnesses
use to put the ST's records into it and read them back.

Where things live (`src/memory.6502`): the drawing in main RAM and HAZEL,
the lists and objects at the top of main RAM, the list phase and the sine
table in the world's bank (5, `src/world.6502`), the shapes in bank 4,
the erase lists in shadow RAM below the shadow screen (an object's box, when
clearing it is cheaper, erased by `src/box.6502` in bank 7: decision 20). Out of
play the loading area (bank 7) holds the front end (FRONT, `src/front.6502`:
the title, the credits, the K screen, the game's end; the start loads it,
and `src/front_main.6502` loads it at a game's end and on Esc, and loads
WINDOW and SPEECH back at a game's start), and the lists and objects hold
the title song (SONG, `src/song.6502`: David Lowe's tune, the Spectrum
128K's player transcribed, playing its own data from `tools/mksongdata.py`),
read beside FRONT, the silo's two records kept in ANDY meanwhile; its tick
and bass edges are `src/song_irq.6502`'s. In play it holds WINDOW: the missile view's
window, its picture (`tools/mkcockpit.py --window`) and the draw phase's
view code (`src/view_under.6502`: the gunsight, the ground dots,
`src/mview.6502`), which runs there with ANDY paged; the bolt and the
shots (`src/view.6502`) run from the logic bank after the step's logic,
from what the logic records for them. `src/engine.6502`
is the frame: the interrupt, the fixed step, the flip (decision 14).
`src/step.6502` is a step of the game in the ST's order (`step_lists`,
`step_logic`), which `make logic` checks whole against the ST's too;
`src/input.6502` is the controls (decision 6): the
vertical sync's interrupt reads the keys into the ST's `key_state` and
`key_latch`, and each step adds the joystick's move to the accumulators
the ST's mouse moves.

- The MOS's IRQ entry keeps A at &FC, so baron's pool stops at &FB, and
  the interrupt handler ends `LDA &FC : RTI`. It must lie below &3000.
- `BANK` writes `bank_now` before ROMSEL, so an interrupt that pages a
  bank and puts `bank_now` back is always right.
- Code in a bank may call main RAM's only if what it calls leaves the
  bank paged as it was (`build_matrix` pages the world's bank, its own).
- The disc (`src/disc.6502`, decision 12) is the game's own 1770 reader,
  a track a read, its NMI routine at &0D00 paging the destination's bank
  for each byte. An interrupt handler that pages a bank must set
  `bank_now` as it does, or a byte arriving then lands in the wrong bank.
- The game logic (`src/logic/`, decision 1) is the ST's exactly, checked
  routine by routine: `tools/st_steps.py` captures the ST's state at each
  boundary of its frame loop, and `tools/logicrun.mjs` runs the port's
  routine from the entry state and compares everything the map holds
  with the exit. The map is the `{ST address kind}` on each variable's
  declaration (`src/vars.6502` says the forms) and the object table
  (`tools/mkobjects.py`). Logic code runs with ANDY paged (ROMSEL bit 7)
  over its bank's first 4K, so it lives at &9000 up; what only the logic
  reads is in ANDY. Keep the ST's d0 in `rng_d0` wherever a random8 call
  adds it: some callers leave it over from earlier work.
- The panel (`src/panel.6502`, its data in `src/panel_data.6502`, below
  the logic in its bank) runs with ANDY paged, called by `panel_draw`
  (`src/cockpit.6502`) after each frame's 3D. Each screen remembers in
  ANDY what its panel shows, so only changes are drawn. What the ST
  prints, the logic records in flags of the port's own (`world_text`,
  `level_text`, `mine_text`, `dock_text`), which the panel draws.
- object_handlers' walk (`src/logic/handlers.6502`) ends at the slot past
  its last, made to look exploding while it runs: no handler may read
  another slot's exploding byte. And it copies random32's state into zero
  page for its own `h_random32`: anything the handlers call takes numbers
  from that, never from random32 or rng32 directly.
- User VIA T1 runs free at the field's period, put in step with the raster
  by `install_irq` alone: nothing else writes its counter, or the split
  moves. Its latch reloads at time-out, so after the split T1 reads the
  next field's count.
- `box_end` logs an object's box onto whichever screen `box_aim` last
  aimed at: call `box_aim` before drawing an object outside
  `view_objects` (Interrogate, the viewer).
- jsbeeb's field is 40,000 cycles (`CYCLES / 50`), not 64 x 312 x 2.
- Code that sets ACCCON's X from main RAM must lie below &3000 (the
  interrupt handler): `ASSERT` it. Code in a bank may set it too (the
  panel, the screens' copy and the window's clear in `src/screen.6502`,
  the boxes' erase), but mustn't read &3000-&7FFF meanwhile: the objects
  and lists are there.
- SG is two parts: the resident code (`Main`, its budget `MAIN_TOP`) and
  `start.6502`, run once after it, which may run on over the lists and
  objects since nothing uses them until `play` clears the objects. Code
  run once at start goes there, not in the resident part. Out of play
  SONG lies there instead: a harness hooking SONG's addresses must wait
  for `song_start`, as the start's code runs at them first.
- The title song's tick (`src/song_irq.6502`) works with interrupts on,
  so what the other interrupts run nests in it: none of that may use a
  `ZA_AUTO` variable (baron gives interrupt routines' variables shared
  places), and the song's pointer is fixed (`song_ptr`). A song interrupt
  ends at once: another waiting comes in again through IRQ1V, which the
  end screen's `band_irq` must see first, for the sync.
- The SN's latch byte and data byte go with interrupts off between them:
  a bass edge's volume byte between would take the data byte.
- FRONT must end below WINDOW's `near_outside`: G's viewer calls it in
  bank 7, where it's left from the last game's WINDOW (`ASSERT`ed).
- A FRONT (bank 7) variable, read by a harness, is at jsbeeb's
  `romOffset + 7 * 16384 + (address - &8000)`, not at its address.
`node tools/scenerun.mjs SCENES OUT --profile 37` samples where the cycles
go. On the disc, `tools/listprof.mjs` splits world_lists into its parts and
`tools/stepprof.mjs` times named routines a step, both holding keys. `tools/missilefps.mjs` times a missile view on the disc, its slide and
its open window.

`tools/fat12.py IMAGE [OUTDIR]` lists or extracts an ST (or PC) floppy,
`tools/adf.py IMAGE [OUTDIR]` an Amiga one.
Run Python that reads the originals with `-I`, from outside `original/`.

The originals run headless, each with its own driver (the research file
says how):

- **The ST**: `tools/st_hatari.py SCRIPT --disk "original/st/Starglider
  (1987)(Rainbird).stx"` on Hatari built in `../hatari` with EmuTOS
  (`../hatari/emutos`). Use the `.stx`: the clean `.st` halts at the
  protection. `tools/st_disasm.py` with `tools/st_star.ctl` is the
  disassembly; `st_shapes.py`, `st_tra.py` and `st_samples.py` pull out
  the shapes, pictures and samples. `st_scenes.py run tests/st/X.txt
  build/scenes/X ...` captures scenes (each frame's state and its lines);
  `st_render.py PRG SCENES` is the renderer modelled exactly, checked
  against them: the port's drawing is checked against the model.
  `st_profile.py run tests/st/profile_flight.txt DIR` profiles the ST and
  splits its time by area (it needs the patched Hatari: research/st.md).
  `st_steps.py run tests/st/steps_X.txt build/steps/X ...` captures the
  logic's state at every routine boundary of the frame loop, and every
  random number call, for the port's logic to be checked routine by
  routine (fly on the keys: random8 adds the mouse accumulator). Set the
  ST's state in such a capture with `poke` lines, which land at a frame's
  start, not `debug w`, which lands wherever the emulation is and shows as
  a difference in whichever routine it falls in. Captures crawl, and more
  slowly with several running at once, so a script's waits count frames
  more than seconds: run them one at a time.
  `st_panel.py run tests/st/panel_X.txt build/stpanel/X ...` captures the
  state the panel draws from and the screen the ST makes, each frame, for
  `node tools/panelcheck.mjs --st build/stpanel/X/panel.json` to check its
  model of the ST's panel against (give Hatari and EmuTOS absolute paths
  from a worktree).
- **The Spectrum 128K**: `tools/zx.py`, nm's harness on SkoolKit.
- **The CPC**: `tools/cpc_emu.py` on the Caprice32 in `../caprice32`.
- **The C64**: `tools/c64_unfreeze.py` and `tools/c64_run.py` on py65.
- **The Master's budgets**: `tools/beeb_linebench.sh` and
  `tools/beeb_soundbench.mjs` in jsbeeb.

## Baron and the 65C12, as met here

- Labels inside a macro are private to each expansion: tables a routine
  must name go in an INCLUDE, not a macro. A FOR body is a scope too.
- Zero page is baron's (`ZA_AUTO`); only what the outside world reads or
  writes, or what lasts, has a fixed address (`src/zp.6502`). Every
  indexed access to a `ZA_AUTO` wants its `ZA_INDEXEDBY`; a patched or
  computed jump wants `ZA_CANJUMP`; an array rebuilt by indexed stores
  wants `ZA_DISCARD`.
- ACCCON's X sends the CPU's own fetches to shadow RAM too: only code
  outside &3000-&7FFF may set it (HAZEL's `line_plot` and `screen_clear`,
  main RAM's below &3000, the panel in its bank).
- A routine that patches code may take X or Y (`line_erase`, `line_draw`):
  reload what you were holding there.
- `ROL` and `ASL` don't touch V; `BIT abs,Y`, `STY abs,X` and `STA zp,Y`
  don't exist (baron says "No such addressing mode" or uses abs,Y).
- `../baron` is shared with `../nm` and `../chuckie-egg-2-beeb`: leave it
  at the release the README names, and try an unreleased baron from a
  build of its own, named by `BARON` in `local.mk`.
- A patched `JSR` wants `ZA_CANCALL`, as a patched `JMP` wants
  `ZA_CANJUMP`. `ZA_DISCARD` takes a whole variable, not an alias for
  part of one.
- A trampoline whose callers share a tail (a JMP to one RTS) merges their
  returns: a ZA result read after one call is live across all their
  paths. Read results inside the trampoline (as `int_sincos` does).
- Front-end code that reaches routines the game shares can raise
  "ZA_AUTO input to a ZA_ENTRY routine": real stores silence it,
  `ZA_DISCARD` doesn't.
- The world bank's list phase is full: room for list-phase code comes from
  moving what only rotate_setup reads into `build/gen/rotate_data.6502`,
  past the sine table, paid for from the world bank's free space.
- Generated code with patched operands: assert that each copy's labels
  sit at the same offsets (`mkrotate.py`) when one routine patches them
  all through a pointer.
- Baron parses the body of a false `IF`: a `FUNCTION` called there must
  exist in both builds (so `ula_entry` is in `defs.6502`), though the
  symbols it names needn't.
- The 6522's T1 reloads from its latch at time-out in one-shot mode too
  (jsbeeb as the chip): after the split, `usrvia_t1ch` reads high again,
  never negative. Never read T1's low counter outside the interrupt: it
  acknowledges T1, and the split can be lost.
- The engine's step is a loop, so a variable baron thinks a step might
  read before writing (a value made only on paths a flag or the carry
  chooses) is kept from step to step, through the drawing and all the
  logic, and the pool runs out. Find it (discard every global at the
  step's top, then all but one) and `ZA_DISCARD` it where it really dies,
  as `ground_dots` does.

## House rules

- `main` is on GitHub (mattgodbolt/starglider-beeb): never force-push it.
  Rebuild `starglider.ssd` with `make disc` when the disc changes.
- Commit messages end at `Co-Authored-By:`. Never include a claude.ai
  session link or a `Claude-Session:` trailer. Never force-push a pushed
  branch.
- Comments and docs carry no figure the build computes or one run
  measured, such as addresses, sizes or free bytes. Name the symbol,
  `ASSERT` the property, or cite the dated decision. (The research and
  the brief record what the originals are, with their own addresses.)
- Never label a statement "honest" or "candid". Size work by what it
  touches, never by time. Use they/them for Matt.
- Before committing, run `make check` on its own and look at its exit
  status: piped through grep in an `&&` chain, a failure goes unseen.
- Agents keep every file they make inside their own worktree, scratch
  under its `build/`, with no symlinks out of it: a path that resolves
  outside stops the run for a permission prompt, and nobody is watching.
- Every agent brief carries these rules.
