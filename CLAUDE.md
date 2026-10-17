# STARGLIDER (BBC Master 128 port) — notes for Claude Code

A port of Argonaut Software's *Starglider* (Rainbird, 1986) to the BBC
Master 128, with Argonaut's blessing. Run the way the Chuckie Egg 2 and
Ninja Massacre ports were
(`../chuckie-egg-2-beeb`, `../nm`), from `../porting-to-the-beeb.md`;
their tools and docs are the model.

- `docs/brief.md`: the brief the port starts from: every version of the
  original, how it works, and the decisions to make first.
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

The ethos is the original's: fast, smooth wireframe vectors. The manual
makes the see-through wireframe part of the fiction (the AGAV's "Enhanced
Vision System" shows "a stunning translucent display of anything within
its visual range, even if objects are behind solid buildings").

## Commands

```sh
make fetch      # download every version into original/ (not committed)
make venv       # .venv (uv sync): SkoolKit, Capstone, Pillow, NumPy
```

`tools/fat12.py IMAGE [OUTDIR]` lists or extracts an ST (or PC) floppy,
`tools/adf.py IMAGE [OUTDIR]` an Amiga one.
Run Python that reads the originals with `-I`, from outside `original/`.

## House rules

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
