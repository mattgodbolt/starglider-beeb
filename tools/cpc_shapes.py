#!/usr/bin/env python3
"""Decode and draw the CPC Starglider shapes, using the original's own code.

    cpc_shapes.py RAM OUTDIR [--yaw N] [--pitch N] [--drop N]

RAM is a 64K (or 128K) dump of the running game taken with tools/cpc_emu.py
(`!ram:NAME`) while in flight, so that the tables in the screen gaps (sine,
squares, logarithms) are in place.

For each object type the shape pointer table at &8F15 names, the original's
object drawer (&4F05: basis routine, vertex program, projection, face culling,
line drawing) is run headlessly (tools/cpc_z80.py) with the object straight
ahead of a level camera. It writes, into OUTDIR:

    shape_NN.png   left: the game's own drawing (its face culling and clipping,
                   read back from the screen buffer); right: every edge in both
                   edge lists, projected from the camera-space vertices the
                   game built, so culled edges show too
    contact.png    all shapes on one sheet
    shapes.md      a table of vertex, edge and face counts and the format fields

The shape record format (see docs/research/cpc.md):

    +0  basis routine address (it rotates and scales the axis vectors)
    +2  size byte (F6C1); the routine may read more size bytes after it
    vertex program: count, then that many ops; op = top 2 bits, slot = low 6
        bits (a 6-byte x,y,z record at &DF00 + 6 x slot): 00 load, 01 store,
        10 midpoint with, 11 add
    projected vertex count (slots 0..n-1 are projected to 4-byte x,y records)
    always-drawn edges: count, then pairs (4 x v1, 4 x v2 | colour)
    culled edges: count, then pairs as above
    faces: count, then per face: 3 vertex refs (orientation test), edge count,
        edge offsets (2 x edge number) into the culled edge list
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cpc_z80 import CPCSimulator, run_call  # noqa: E402
from skoolkit.simutils import IXh, IXl, IYh, IYl, PC, SP  # noqa: E402

SHAPE_TABLE = 0x8F15
OBJ = 0x7600          # first object record (20 bytes); borrowed for the drawing
VIEW_W, VIEW_H = 256, 128
# The flight palette (inks 1-3 from &F61D-&F61F at VSync): bright red,
# bright green, bright cyan on black.
PALETTE = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 255, 255)]


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


class Game:
    def __init__(self, ram):
        self.mem = bytearray(ram[:65536])
        self.sim = CPCSimulator(self.mem)
        self.base = bytes(self.mem)

    def r16(self, a):
        return self.mem[a] | self.mem[a + 1] << 8

    def w16(self, a, v):
        self.mem[a] = v & 0xFF
        self.mem[a + 1] = (v >> 8) & 0xFF

    def reset(self):
        self.mem[:] = self.base
        for a in (0xF6A1, 0xF6A3, 0xF6A5):      # camera yaw, pitch, roll
            self.w16(a, 0)
        for r in (0x3E0F, 0x3DF8, 0x3E26):      # their sines and cosines
            run_call(self.sim, r)
        self.mem[0xF62D] = 0                     # not the missile camera view
        self.mem[0xF6DA], self.mem[0xF6DB] = 0, 0xC0   # draw into &C000
        for ras in range(8):
            base = 0xC000 + ras * 0x800
            self.mem[base + 0x40:base + 0x440] = bytes(0x400)

    def run_to(self, stop, limit=2_000_000):
        regs = self.sim.registers
        n = 0
        while regs[PC] != stop:
            self.sim.run()
            n += 1
            if n > limit:
                raise RuntimeError(f"stuck at &{regs[PC]:04X}")
        return n

    def draw(self, t, yaw, pitch, z, drop=0, colour=3):
        """Draw type t at camera-space (0, drop * z / 256, z). Returns the capture dict."""
        self.reset()
        m = self.mem
        m[OBJ + 7], m[OBJ + 8] = pitch & 0xFF, yaw & 0xFF
        self.w16(0xF6BB, 0)
        self.w16(0xF6BD, drop * z // 256)
        self.w16(0xF6BF, z)
        m[0xF61B] = colour
        shape = self.r16(SHAPE_TABLE + 2 * t)
        regs = self.sim.registers
        regs[IXh], regs[IXl] = shape >> 8, shape & 0xFF
        regs[IYh], regs[IYl] = OBJ >> 8, OBJ & 0xFF
        sp = 0xFE00 - 2
        m[sp], m[sp + 1] = 0xFE, 0xFF
        regs[SP] = sp
        regs[PC] = 0x4F05
        steps = self.run_to(0x4F1B)              # basis routine done
        prog = regs[IXh] << 8 | regs[IXl]
        steps += self.run_to(0x3C18)             # vertex program done
        nproj = m[0xF6BA]
        verts = [tuple(s16(self.r16(0xDF00 + 6 * i + 2 * k)) for k in range(3)) for i in range(64)]
        steps += self.run_to(0x4AC4)             # projection done
        proj = [(s16(self.r16(0xDF00 + 4 * i)), s16(self.r16(0xDF02 + 4 * i))) for i in range(nproj)]
        steps += self.run_to(0xFFFE)
        return {"shape": shape, "prog": prog, "nproj": nproj, "verts": verts[:max(nproj, 1)],
                "proj": proj, "steps": steps, "screen": self.screen()}

    def screen(self):
        im = Image.new("RGB", (VIEW_W, VIEW_H))
        px = im.load()
        for y in range(VIEW_H):
            row = y + 8
            a = 0xC000 + (row // 8) * 64 + (row % 8) * 0x800
            for xb in range(64):
                b = self.mem[a + xb]
                for n in range(4):
                    c = ((b >> (7 - n)) & 1) | (((b >> (3 - n)) & 1) << 1)
                    px[xb * 4 + n, y] = PALETTE[c]
        return im


def parse(mem, prog):
    """Walk a shape's vertex program, edge lists and faces from its start."""
    p = prog
    nops = mem[p]
    ops = list(mem[p + 1:p + 1 + nops])
    p += 1 + nops
    nproj = mem[p]
    p += 1
    nalways = mem[p]
    always = [(mem[p + 1 + 2 * i], mem[p + 2 + 2 * i]) for i in range(nalways)]
    p += 1 + 2 * nalways
    nedges = mem[p]
    edges = [(mem[p + 1 + 2 * i], mem[p + 2 + 2 * i]) for i in range(nedges)]
    p += 1 + 2 * nedges
    nfaces = mem[p]
    p += 1
    faces = []
    for _ in range(nfaces):
        tri = tuple(mem[p:p + 3])
        k = mem[p + 3]
        faces.append((tri, list(mem[p + 4:p + 4 + k])))
        p += 4 + k
    slots = set()
    for op in ops:
        slots.add(op & 0x3F)
    return {"ops": ops, "nproj": nproj, "always": always, "edges": edges, "faces": faces,
            "end": p, "slots": slots}


def wireframe(cap, info):
    """Every edge, projected from the game's camera-space vertices."""
    im = Image.new("RGB", (VIEW_W, VIEW_H))
    d = ImageDraw.Draw(im)
    # The game's own projection (x, y in view pixels), so the two halves line up.
    proj = cap["proj"]
    for v1, v2 in info["always"] + info["edges"]:
        a, b = v1 >> 2, v2 >> 2
        col = v2 & 3 or 3
        if a >= len(proj) or b >= len(proj):
            continue
        pa, pb = proj[a], proj[b]
        if pa[0] == -0x8000 or pb[0] == -0x8000:
            continue
        d.line([pa, pb], fill=PALETTE[col])
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ram", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--yaw", type=lambda s: int(s, 0), default=0x20)
    ap.add_argument("--pitch", type=lambda s: int(s, 0), default=0,
                    help="the object's pitch byte (IY+7); some animated shapes use it as their phase")
    ap.add_argument("--drop", type=int, default=-16,
                    help="camera-space height of the object, in 256ths of its distance (to look down on it)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    game = Game(args.ram.read_bytes())
    m = game.base
    rows = []
    tiles = []
    for t in range(64):
        shape = m[SHAPE_TABLE + 2 * t] | m[SHAPE_TABLE + 2 * t + 1] << 8
        if not 0x0200 <= shape < 0x14F4:
            break
        routine = m[shape] | m[shape + 1] << 8
        if routine < 0x1500:          # type 28, the silo interior, has no basis routine
            rows.append((t, shape, routine, None, None))
            continue
        try:
            # Fit: the nearest distance (in steps of an eighth) at which every
            # vertex projects inside the view with a small margin.
            cap = None
            for i in range(48):
                z = int(150 * 2 ** (i / 8))
                cap = game.draw(t, args.yaw, args.pitch, z, args.drop)
                if all(p[0] != -0x8000 and 6 <= p[0] < VIEW_W - 6 and 4 <= p[1] < VIEW_H - 4
                       for p in cap["proj"]):
                    break
            info = parse(game.base, cap["prog"])
        except Exception as e:  # noqa: BLE001 - report and carry on
            rows.append((t, shape, routine, None, str(e)))
            continue
        left = cap["screen"]
        right = wireframe(cap, info)
        tile = Image.new("RGB", (VIEW_W * 2 + 8, VIEW_H + 16), (40, 40, 40))
        tile.paste(left, (0, 16))
        tile.paste(right, (VIEW_W + 8, 16))
        ImageDraw.Draw(tile).text((4, 2), f"type {t}  &{shape:04X}  routine &{routine:04X}  z={z}", fill=(255, 255, 255))
        tile.save(args.out / f"shape_{t:02d}.png")
        tiles.append(tile)
        rows.append((t, shape, routine, (cap, info, z), None))
    # Contact sheet: two tiles per row.
    if tiles:
        tw, th = tiles[0].size
        cols = 2
        sheet = Image.new("RGB", (cols * (tw + 8), ((len(tiles) + cols - 1) // cols) * (th + 8)), (20, 20, 20))
        for i, tile in enumerate(tiles):
            sheet.paste(tile, ((i % cols) * (tw + 8), (i // cols) * (th + 8)))
        sheet.save(args.out / "contact.png")
    with open(args.out / "shapes.md", "w") as f:
        f.write("| type | record | basis routine | sizes | ops | vertices (projected) | always edges | "
                "culled edges | faces | record bytes |\n|---|---|---|---|---|---|---|---|---|---|\n")
        for t, shape, routine, res, err in rows:
            if res is None:
                f.write(f"| {t} | &{shape:04X} | &{routine:04X} | | | | | | | {err or 'not drawn here'} |\n")
                continue
            cap, info, z = res
            sizes = " ".join(f"{b}" for b in m[shape + 2:cap["prog"]])
            f.write(f"| {t} | &{shape:04X} | &{routine:04X} | {sizes} | {len(info['ops'])} | {info['nproj']} | "
                    f"{len(info['always'])} | {len(info['edges'])} | {len(info['faces'])} | "
                    f"{info['end'] - shape} |\n")
    for t, shape, routine, res, err in rows:
        if res:
            cap, info, z = res
            print(f"type {t:2d} &{shape:04X} &{routine:04X}: {len(info['ops']):3d} ops, {info['nproj']:2d} vertices, "
                  f"{len(info['always'])} always + {len(info['edges'])} culled edges, {len(info['faces'])} faces, "
                  f"{info['end'] - shape} bytes, {cap['steps']} instructions")
        else:
            print(f"type {t:2d} &{shape:04X} &{routine:04X}: {err or 'not drawn'}")


if __name__ == "__main__":
    main()
