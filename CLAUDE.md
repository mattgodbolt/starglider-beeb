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
- `docs/research/*.md`: the reverse engineering, one file per version.
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
make check      # the sine table against the ST's, make spike, and the
                # disc's erasing (tools/erasecheck.mjs)
make scenes     # capture the scenes in Hatari (slow; needs ../hatari)
make fetch      # download every version into original/ (not committed)
make venv       # .venv (uv sync): SkoolKit, Capstone, Pillow, NumPy
```

The build makes the shapes and per-type tables from the ST's STAR.PRG
(`tools/mkshapes.py`) and generates the line drawer, the camera rotation
and the vertex transforms (`tools/mkline.py`, `mkrotate.py`,
`mkxform.py`) into `build/gen/`; baron computes the sine table
(`src/sine.6502`) and the multiply and reciprocal tables.
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
- ACCCON's X sends the CPU's own fetches to shadow RAM too: only code in
  HAZEL may set it (`line_plot`, `screen_clear`).
- A routine that patches code may take X or Y (`line_erase`, `line_draw`):
  reload what you were holding there.
- `ROL` and `ASL` don't touch V; `BIT abs,Y`, `STY abs,X` and `STA zp,Y`
  don't exist (baron says "No such addressing mode" or uses abs,Y).
- Generated code with patched operands: assert that each copy's labels
  sit at the same offsets (`mkrotate.py`) when one routine patches them
  all through a pointer.

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
- Every agent brief carries these rules.
