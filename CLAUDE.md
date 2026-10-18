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
                # (tools/disccheck.mjs) and its controls (tools/inputcheck.mjs)
make logic      # the port's game logic against the ST's, routine by routine
                # and a whole step (tools/logicrun.mjs, on the captures make
                # steps makes)
make panel      # the panel drawn from those captures' frames, every pixel
                # against a model of the ST's formulas (tools/panelcheck.mjs;
                # --png DIR --at CAPTURE:FRAME renders, --colours an option)
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
the erase lists in shadow RAM below the shadow screen. `src/engine.6502`
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
- Code that sets ACCCON's X from main RAM must lie below &3000
  (`src/cockpit.6502`, the interrupt handler): `ASSERT` it. Code in a
  bank may set it too (the panel), but mustn't read &3000-&7FFF meanwhile:
  the objects and lists are there.
`node tools/scenerun.mjs SCENES OUT --profile 37` samples where the cycles
go.

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
- Baron matches ZA_CANJUMP, ZA_CANCALL and the other control-flow
  annotations to their jumps by address alone (waitingforvsync/baron#29):
  in banks that share addresses, an annotated jump in one lends its
  targets to any jump at the same address in another. Keep annotated
  jumps' addresses clear of the other banks' code (the logic bank starts
  past the world bank's list phase), or route them through main RAM.
  Issue #1 lists the workarounds to undo once it's fixed: add to it.
- A list symbol as a ZA_CANJUMP or ZA_CANCALL target resolves its labels
  only in the annotation's own section (waitingforvsync/baron#30): name
  targets in another section one by one (`tools/mkhandlers.py` writes
  the handlers' dispatch so).
- A patched `JSR` wants `ZA_CANCALL`, as a patched `JMP` wants
  `ZA_CANJUMP`. `ZA_DISCARD` takes a whole variable, not an alias for
  part of one.
- Generated code with patched operands: assert that each copy's labels
  sit at the same offsets (`mkrotate.py`) when one routine patches them
  all through a pointer.
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
- Every agent brief carries these rules.
