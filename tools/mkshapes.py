#!/usr/bin/env python3
"""The ST's shapes as Baron source, for the port.

    mkshapes.py PRG OUTDIR      write OUTDIR/shapes.6502 and OUTDIR/types.6502

PRG is the ST's AUTO/STAR.PRG (tools/fat12.py takes it off the disc). The
build runs this: nothing derived from the original is committed.

**Shapes** (docs/decisions.md, decision 9). Every coordinate of a shape
is a multiple of its gcd g, so a vertex is three signed bytes k with
v = g * k, and g / 32 is the shape's `scale`. The energy beam is the one
exception: its coordinates (multiples of 128, up to 32,000) are rounded
to multiples of 256. An animation list may name a frame more than once;
each frame is kept once. Shape 10 is the Walker's data again, as on the
ST.

Each face carries its normal in object space, as the ST would compute it
from its first three vertices ((v1 - v0) x (v2 - v0)), scaled so its
largest component is 127, and K, the normal's dot product with vertex 2
in world units (shape units / 16), kept in fours. The face is visible
when the camera's position in object space, c, in world units, has
n.c > 4K: the ST's test (n.v2 < 0 in camera space) moved into object
space, where it costs three products a face and no vertex transforms. A
face whose three vertices are in a line has n = 0 and K = 0 and is never
visible, as on the ST.

Vertices are renumbered with the ones no frame moves first (`nstill` of
them), and faces with the ones whose normal no frame changes first
(`nrigid`), so those are kept once for the shape and a frame holds only
the rest. The layout, every list a byte an entry:

    shape_lo, shape_hi   each shape's header, by shape number
    header   nverts nedges nfaces colour scale nframes nstill nrigid, the
             radius (a word: world units, rounded up), then the
             addresses of: frames (a word per animation-list entry),
             ev0 ev1 (each edge's two vertices), fflags (bit 7: always
             visible), fedges (each face's offset into edgelists),
             edgelists (a count, then the edges, per face), vx vy vz (the
             still vertices), nx ny nz (the rigid faces' normals)
    frame    vx vy vz (the moving vertices), nx ny nz (the other faces'
             normals), Klo Khi (every face's K)

`colour` is the ST's colour (the last face's), which the port maps to its
own; &FF is the beam's, which cycles (animate_shapes, &044F4).
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402
import st_shapes  # noqa: E402

BEAM = 11
BEAM_G = 256
K_UNIT = 4                          # K is kept in fours of n x world units


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def equb(label, values):
    """A label and its bytes; an empty list takes no room."""
    out = [f".{label}"]
    for i in range(0, len(values), 16):
        out.append("    EQUB " + ", ".join(str(v) for v in values[i:i + 16]))
    return out


def shape_source(s, alias=None):
    k = s["index"]
    out = [f"; shape {k}"]
    if alias is not None:
        out.append(f"shape{k} = shape{alias}           ; the same data, as on the ST")
        return out
    frames = s["frames"] or [s["verts"]]
    coords = [c for fr in frames for v in fr for c in v]
    if k == BEAM:
        g = BEAM_G
    else:
        g = 0
        for c in coords:
            g = math.gcd(g, c)
        g = g or 32
    assert g % 32 == 0, (k, g)
    assert g // 32 < 16, (k, g)                    # draw_shape scales by 16 x scale, a byte
    nv, ne, nf = s["nverts"], s["nedges"], s["nfaces"]
    # The frames the animation list names, each kept once (the list may
    # name one more than once); frame_index maps the list's entries.
    unique, frame_index = [], []
    for fr in frames:
        key = tuple(map(tuple, fr))
        if key not in unique:
            unique.append(key)
        frame_index.append(unique.index(key))
    # Still vertices first, then those that move; faces whose normal never
    # changes first, then the rest. Edges and faces are renumbered to match.
    still = [i for i in range(nv) if len({fr[i] for fr in unique}) == 1]
    vorder = still + [i for i in range(nv) if i not in still]
    vnew = {old: new for new, old in enumerate(vorder)}

    def normal(fr, f):
        v0, v1, v2 = (fr[j] for j in f["verts"][:3])
        n = cross(sub(v1, v0), sub(v2, v0))
        big = max(abs(c) for c in n)
        return (tuple(round(c * 127 / big) for c in n) if big else (0, 0, 0)), v2

    rigid = [j for j, f in enumerate(s["faces"]) if len({normal(fr, f)[0] for fr in unique}) == 1]
    forder = rigid + [j for j in range(nf) if j not in rigid]
    faces = [s["faces"][j] for j in forder]
    colour = s["faces"][-1]["colour"] & 15 if s["faces"] else 0
    if k == BEAM:
        colour = 0xFF                               # animate_shapes cycles it
    # the radius in world units, rounded up: how far any frame's vertex
    # (as the port has it, g k) is from the object's centre
    radius = math.ceil(max(math.sqrt(sum((round(c / g) * g) ** 2 for c in v)) for fr in unique for v in fr) / 16)
    out.append(f".shape{k}")
    out.append(f"    EQUB {nv}, {ne}, {nf}, {colour}, {g // 32}, {len(frames)}, {len(still)}, {len(rigid)}")
    out.append(f"    EQUW {radius}")
    out.append(f"    EQUW shape{k}_frames, shape{k}_ev0, shape{k}_ev1, shape{k}_fflags, shape{k}_fedges, "
               f"shape{k}_edgelists, shape{k}_vx, shape{k}_vy, shape{k}_vz, shape{k}_nx, shape{k}_ny, shape{k}_nz")
    out.append(f".shape{k}_frames")
    out.append("    EQUW " + ", ".join(f"shape{k}_f{i}" for i in frame_index))
    out += equb(f"shape{k}_ev0", [vnew[a] for a, _ in s["edges"]] or [0])
    out += equb(f"shape{k}_ev1", [vnew[b] for _, b in s["edges"]] or [0])
    out += equb(f"shape{k}_fflags", [0x80 if f["always"] else 0 for f in faces] or [0])
    lists, offs = [], []
    for f in faces:
        offs.append(len(lists))
        lists += [len(f["edges"])] + f["edges"]
    assert len(lists) < 256, (k, len(lists))
    out += equb(f"shape{k}_fedges", offs or [0])
    out += equb(f"shape{k}_edgelists", lists or [0])
    ks = lambda fr, idx: [[round(fr[i][a] / g) for i in idx] for a in range(3)]
    base = ks(unique[0], vorder[:len(still)])
    for a, name in enumerate("xyz"):
        out += equb(f"shape{k}_v{name}", [x & 0xFF for x in base[a]] or [0])
    bn = [normal(unique[0], f)[0] for f in faces[:len(rigid)]]
    for a, name in enumerate("xyz"):
        out += equb(f"shape{k}_n{name}", [n[a] & 0xFF for n in bn] or [0])
    for i, fr in enumerate(unique):
        moving = ks(fr, vorder[len(still):])
        assert all(-127 <= x <= 127 for axis in moving + base for x in axis), (k, i)
        ns = [normal(fr, f) for f in faces]
        K = [round(sum(a * b for a, b in zip(n, v2)) / 16 / K_UNIT) for n, v2 in ns]
        assert all(-0x8000 <= x < 0x8000 for x in K), (k, i)
        out.append(f".shape{k}_f{i}")
        # A frame's arrays follow one another; the renderer finds each by
        # the lengths before it, so an empty one takes no room.
        for a, name in enumerate("xyz"):
            out += equb(f"shape{k}_f{i}_v{name}", [x & 0xFF for x in moving[a]])
        for a, name in enumerate("xyz"):
            out += equb(f"shape{k}_f{i}_n{name}", [n[a] & 0xFF for n, _ in ns[len(rigid):]])
        out += equb(f"shape{k}_f{i}_Klo", [x & 0xFF for x in K])
        out += equb(f"shape{k}_f{i}_Khi", [(x >> 8) & 0xFF for x in K])
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    prg = st_prg.load(sys.argv[1])
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    shapes = st_shapes.load_shapes(prg)
    src = ["; Generated by tools/mkshapes.py from the ST's STAR.PRG: do not edit.",
           f"SHAPES = {len(shapes)}"]
    body = []
    first = {}
    for s in shapes:
        if s["nverts"]:
            key = s["verts_at"]
            body += shape_source(s, first.get(key))
            first.setdefault(key, s["index"])
    names = [f"shape{s['index']}" if s["nverts"] else "0" for s in shapes]
    src += [".shape_lo", "    EQUB " + ", ".join(f"LO({n})" for n in names),
            ".shape_hi", "    EQUB " + ", ".join(f"HI({n})" for n in names)]
    src += body
    (outdir / "shapes.6502").write_text("\n".join(src) + "\n")
    # The per-type tables the renderer reads: type to shape (&0AC76) and the
    # draw list's "wholly behind" size (&0ACB6), 32 types each.
    types = ["; Generated by tools/mkshapes.py from the ST's STAR.PRG: do not edit.",
             ".type_shape", "    EQUB " + ", ".join(str(prg.u16(0x0AC76 + 2 * t)) for t in range(32)),
             ".size_z_lo", "    EQUB " + ", ".join(str(prg.u8(0x0ACB6 + 2 * t + 1)) for t in range(32)),
             ".size_z_hi", "    EQUB " + ", ".join(str(prg.u8(0x0ACB6 + 2 * t)) for t in range(32))]
    (outdir / "types.6502").write_text("\n".join(types) + "\n")


if __name__ == "__main__":
    main()
