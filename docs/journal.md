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
