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
