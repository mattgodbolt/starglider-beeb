#!/usr/bin/env python3
"""Extract and draw Starglider 128's shapes with the Spectrum original's own code.

    .venv/bin/python tools/zx_shapes.py [--snap build/zx128.z80] [--out docs/images/zx] [--json FILE]

For each object type (0-35; the shape table is at &6DCE in bank 5) this
calls the game's object drawer, &D3AC, on a made-up object straight ahead
of the viewer with every angle zero (the viewer's heading, pitch and roll
and the object's yaw), from a stub with interrupts off and bank 0 paged.
The whole call is timed (with contention, as drawn at about half the
window's height). It stops at &D307, after the shape's vertex program (&D0DA) has built the
camera-space vertices at &4B00 (x right, y down, z ahead; 6 bytes each),
and at &D314, after &C08B has projected them, then lets the drawer finish,
which leaves the game's own picture of the shape in the 256x128 view
buffer (bank 7, &E800). The lists after the vertex program are parsed
(docs/research/zx.md, "Shapes"):

    P                 vertices to project (slots 0..P-1)
    E1, E1 x (a, b)   edges always drawn
    E2, E2 x (a, b)   edges drawn when a face that lists them faces the viewer
    F, F x (v1 v2 v3 n e1..en)   faces: three vertices for the facing test,
                      and the byte offsets of their edges in the E2 list

An edge byte's bits 7-2 are the vertex slot x 4; bit 1 of the first byte
and bits 1-0 of the second make the ink (0: the object's own colour).

Writes, per type, shape_NN.png (the game's render, cropped to the 240x120
window the screen shows, then front, side and top views of the edges) and a
contact sheet, shapes.png. --json dumps vertices, edges and faces (for
comparing versions; the data is Rainbird's, so keep it out of the repository).
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zx import Spectrum, run_script  # noqa: E402
from skoolkit.simutils import IXh, IXl, PC, T  # noqa: E402

SHAPE_TABLE = 0x6DCE
N_TYPES = 36
DRAW_OBJECT = 0xD3AC
AFTER_VERTICES = 0xD307   # back from the vertex program (&D0DA) in &D304
AFTER_PROJECT = 0xD314    # back from the projection (&C08B)
VERTS = 0x4B00
OBJ = 0x4C00              # object table slot 0 (this is a throwaway copy of the game)
NODE = 0x4A80             # a depth-tree node: z at +0, the object's address at +4
STUB = 0x4A40
BUFFER = 0x2800           # &E800 in bank 7: the 256x128 view buffer, 32 bytes a line
ATTRS = 0x3800            # &F800 in bank 7: its attributes
DIST = 1000               # where the shape is put to read its vertices

# The silo computer's file (&8688) and the mission targets (&B434) name these.
NAMES = {1: "Pyramid Proximity Mine", 11: "Diamond Proximity Mine", 7: "Walker",
         2: "Energy Tower", 8: "Starglider Drone", 5: "Armoured Transport Vehicle",
         6: "Egron Battle Tank", 16: "Egron Neutron Missile", 10: "Bute Fighter",
         22: "Stomper", 12: "Skim Fighter", 13: "Juno Cannon", 14: "Lotus Starfighter",
         15: "Tri Launcher", 20: "Pyramid Launcher", 17: "Egron Homing Missile",
         18: "Diamonic Shuttle", 23: "Starglider One", 25: "Battle Crawler",
         29: "Rear View Scanner", 28: "Energy Pod", 27: "Super Missile",
         26: "Ammunition Dump", 30: "Command Centre"}

INKS = [(0, 230, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255),
        (255, 255, 0), (255, 255, 255)]


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def word(mem, a):
    return mem[a] | mem[a + 1] << 8


def setup(spec, t, z):
    """Put a white object of type t at distance z, and the stub that draws it."""
    mem = spec.mem
    for i in range(20):
        mem[OBJ + i] = 0
    mem[OBJ + 0] = 0xE0       # bits 7-5: the object's ink
    mem[OBJ + 9] = t
    for i in range(6):
        mem[NODE + i] = 0
    mem[NODE + 0], mem[NODE + 1] = z & 0xFF, z >> 8
    mem[NODE + 4], mem[NODE + 5] = OBJ & 0xFF, OBJ >> 8
    for a in range(0x56B0, 0x56B6):    # the viewer's heading, pitch and roll
        mem[a] = 0
    for a in (0x56F2, 0x56F4, 0x56F6, 0x56F8, 0x56FA):   # their sines and cosines
        mem[a], mem[a + 1] = 0, 0x7F
    mem[0x5637] = 0                    # not the missile view
    stub = [0xF3,                                        # DI
            0x31, 0xF0, 0x7F,                            # LD SP,&7FF0
            0x3E, 0x00, 0xCD, 0x49, 0x85,                # LD A,0: CALL &8549 (page bank 0)
            0x21, (NODE + 4) & 0xFF, (NODE + 4) >> 8,    # LD HL,NODE+4
            0xCD, DRAW_OBJECT & 0xFF, DRAW_OBJECT >> 8,  # CALL &D3AC
            0x18, 0xFE]                                  # JR $
    for i, b in enumerate(stub):
        mem[STUB + i] = b
    bank7 = mem.banks[7]
    bank7[BUFFER:BUFFER + 0x1000] = bytes(0x1000)
    bank7[ATTRS:ATTRS + 0x200] = bytes(0x200)
    spec.sim.registers[PC] = STUB
    return STUB + len(stub) - 2


def draw(snap, t, z, cmio=False):
    """Run the drawer on type t at distance z: (vertices, IX after the vertex
    program, projected X and Y of slots 0..41, the view buffer, T-states the
    whole call took), or None."""
    spec = Spectrum(snap, cmio=cmio)
    end = setup(spec, t, z)
    mem = spec.mem
    t0 = spec.sim.registers[T]
    if spec.run_tstates(50 * spec.frame, stop=AFTER_VERTICES) != AFTER_VERTICES:
        return None
    r = spec.sim.registers
    ix = r[IXl] | r[IXh] << 8
    verts = [(s16(word(mem, VERTS + 6 * i)), s16(word(mem, VERTS + 6 * i + 2)),
              s16(word(mem, VERTS + 6 * i + 4))) for i in range(42)]
    proj = None
    if spec.run_tstates(50 * spec.frame, stop=AFTER_PROJECT) == AFTER_PROJECT:
        proj = [(s16(word(mem, VERTS + 4 * i)), s16(word(mem, VERTS + 4 * i + 2))) for i in range(42)]
    spec.run_tstates(50 * spec.frame, stop=end)
    buf = bytes(mem.banks[7][BUFFER:BUFFER + 0x1000])
    return verts, ix, proj, buf, spec.sim.registers[T] - t0


def parse_lists(mem, ix):
    """The lists after the vertex program, from IX at &D307."""
    p = mem[ix]
    ix += 1
    lists = []
    for _ in range(2):
        n = mem[ix]
        ix += 1
        edges = []
        for i in range(n):
            a, b = mem[ix + 2 * i], mem[ix + 2 * i + 1]
            edges.append((a >> 2, b >> 2, ((a & 2) << 1) | (b & 3)))
        lists.append(edges)
        ix += 2 * n
    nf = mem[ix]
    ix += 1
    faces = []
    for _ in range(nf):
        n = mem[ix + 3]
        faces.append({"test": [mem[ix] >> 2, mem[ix + 1] >> 2, mem[ix + 2] >> 2],
                      "edges": [mem[ix + 4 + i] // 2 for i in range(n)]})
        ix += 4 + n
    return p, lists[0], lists[1], faces, ix


def views(verts, edges, size=128):
    """Front (x right, y down), side (z right, y down) and top (x right,
    z up) views of the edges, scaled together to fit size x size cells."""
    im = Image.new("RGB", (3 * size, size), (0, 0, 0))
    d = ImageDraw.Draw(im)
    used = {v for e in edges for v in e[:2]}
    if not used:
        return im
    span = max(abs(c) for v in used for c in verts[v]) or 1
    s = (size / 2 - 4) / span
    for k, (ax, ay, sy) in enumerate([(0, 1, 1), (2, 1, 1), (0, 2, -1)]):
        ox, oy = k * size + size / 2, size / 2
        d.rectangle([k * size, 0, k * size + size - 1, size - 1], outline=(48, 48, 48))
        for a, b, ink in edges:
            pa, pb = verts[a], verts[b]
            d.line([ox + pa[ax] * s, oy + sy * pa[ay] * s, ox + pb[ax] * s, oy + sy * pb[ay] * s],
                   fill=INKS[ink])
    return im


def buffer_image(buf):
    """The 240x120 part of the view buffer that the screen shows."""
    im = Image.new("RGB", (240, 120))
    px = im.load()
    for y in range(8, 128):
        for x in range(8, 248):
            if buf[y * 32 + x // 8] & (0x80 >> (x & 7)):
                px[x - 8, y - 8] = (0, 230, 0)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/zx128.z80")
    ap.add_argument("--pre", default="f50,ENTER:tap,f100",
                    help="zx.py steps that get the game flying before drawing")
    ap.add_argument("--out", default="docs/images/zx")
    ap.add_argument("--json")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = Spectrum(args.snap)
    run_script(base, args.pre, "shots/zx_")
    snap = str(out / ".zx_shapes_base.z80")
    base.save(snap)
    shapes, tiles, focal = {}, [], []
    try:
        for t in range(N_TYPES):
            p = word(base.mem, SHAPE_TABLE + 2 * t)
            routine = word(base.mem, p)
            info = {"type": t, "name": NAMES.get(t, ""), "addr": f"&{p:04X}", "routine": f"&{routine:04X}"}
            shapes[t] = info
            if t == 0x20:
                info["note"] = "drawn by &D7B8, not from the shape table"
                continue
            if routine < 0xC000:
                info["note"] = f"no draw routine (&{routine:04X})"
                continue
            r = draw(snap, t, DIST)
            if r is None:
                info["note"] = "did not reach &D307"
                continue
            verts, ix, proj = r[:3]
            pnum, e1, e2, faces, end = parse_lists(base.mem, ix)
            obj = [(x, y, z - DIST) for x, y, z in verts]
            edges = e1 + e2
            used = {v for e in edges for v in e[:2]}
            span = max((abs(c) for v in used for c in obj[v]), default=1)
            for v in used:
                x, y, z = verts[v]
                if proj and z > 0 and x:
                    focal.append((proj[v][0] - 128) * z / x)
            # Far enough that the shape fills about half the window.
            fit = max(200, span * 5)
            drawn = draw(snap, t, fit, cmio=True)
            game = buffer_image(drawn[3])
            info["tstates"] = drawn[4]
            info.update(vertices=pnum, edges_always=len(e1), edges_culled=len(e2), faces=len(faces),
                        bytes=end - p, header=" ".join(f"{base.mem[p + i]:02X}" for i in range(6)),
                        xyz=obj[:pnum], box=obj[34:42], edges=[list(e) for e in edges], face_list=faces,
                        drawn_at=fit)
            v = views(obj, edges)
            tile = Image.new("RGB", (240 + 8 + v.width, 18 + 128), (0, 0, 0))
            tile.paste(game, (0, 18 + 4))
            tile.paste(v, (248, 18))
            d = ImageDraw.Draw(tile)
            label = f"{t}: {NAMES.get(t, '?')}  ({pnum} vertices, {len(e1) + len(e2)} edges"
            label += f", {len(faces)} faces)" if faces else ")"
            d.text((2, 3), label, fill=(255, 255, 0))
            tile.save(out / f"shape_{t:02d}.png")
            tiles.append(tile)
            print(f"type {t:2d} &{p:04X} routine &{routine:04X}: {pnum:2d} vertices, {len(e1):2d}+{len(e2):2d} "
                  f"edges, {len(faces):2d} faces, {end - p:3d} bytes, half-size {span:4d}, {drawn[4]:6d} T  "
                  f"{NAMES.get(t, '')}")
    finally:
        Path(snap).unlink()
    if focal:
        focal.sort()
        print(f"projection: X = 128 + x*K/z with K ~ {focal[len(focal) // 2]:.1f} (median of {len(focal)})")
    if tiles:
        w, h = tiles[0].width, tiles[0].height
        cols = 2
        sheet = Image.new("RGB", (cols * w + 8, ((len(tiles) + cols - 1) // cols) * h), (0, 0, 0))
        for i, tile in enumerate(tiles):
            sheet.paste(tile, ((i % cols) * (w + 8), (i // cols) * h))
        sheet.save(out / "shapes.png")
    if args.json:
        Path(args.json).write_text(json.dumps(shapes, indent=1))


if __name__ == "__main__":
    sys.exit(main())
