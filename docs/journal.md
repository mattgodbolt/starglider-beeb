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
