#!/usr/bin/env python3
"""Decode and draw the C64 Starglider's shapes (Solid Image's format).

    c64_shapes.py RAM.bin OUTDIR [--base 0900] [--count 27] [--prefix c64]

RAM.bin is a 64K image (c64_unfreeze.py's ram.bin, or the Apple II image from
a2_image.py, whose shape directory sits elsewhere: pass --base). The format,
read from the engine's loader at &24CE/&2507 and vertex reader &277C:

  directory at BASE: COUNT entries of four bytes, two offsets from BASE to a
  shape header (the engine takes the second when asked for variant 5; every
  entry here has both the same).
  shape header: vertices, edges, faces (totals, checked against buffer space),
  two bytes not read by the loader, parts, then per part eight bytes: offset
  of the part from BASE, three bytes the loader keeps in &31-&33, and three
  shift counts for X, Y and Z.
  part: vertices nv, edges ne, faces nf; nf face bytes (a first edge per
  face); ne edge start vertices; ne edge end vertices; ne left faces; ne right
  faces; nv vertices of three signed bytes (X, Y, Z), each shifted left by its
  axis's count; ne next-edge links for the left face; ne for the right face.
  Indices are 0-based within the part.

It writes OUTDIR/PREFIX_shape_NN.png (a perspective view and three
orthographic views), OUTDIR/PREFIX_shapes.png (a contact sheet) and prints a
table of vertex, edge and face counts and extents. --json also dumps
OUTDIR/PREFIX_shapes.json.
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw


# Names from the interrogation screen: its index (&5C80) is the shape number,
# written as the type byte (index x 4) of the displayed object at &1C02, and
# its name table is the split pointer list at &D84B/&D85D (C64 addresses).
NAMES = {
    0: "Armoured transport vehicle", 1: "Egron battle tank", 2: "Walker",
    3: "Starglider drone", 4: "StarGlider One", 5: "Bute fighter",
    6: "Lotus starfighter", 7: "Stomper", 8: "Diamond proximity mine",
    9: "Pyramid mine", 10: "Message pod", 11: "Egron neutron missile",
    12: "Egron homing missile", 13: "Juno cannon", 14: "Tri-launcher",
    16: "Pyramid launcher", 22: "Energy tower",
}


def s8(b):
    return b - 256 if b & 0x80 else b


def decode(ram, base, count):
    shapes = []
    for n in range(count):
        e = base + 4 * n
        off = ram[e] | ram[e + 1] << 8
        h = base + off
        nv, ne, nf = ram[h], ram[h + 1], ram[h + 2]
        extra = ram[h + 3] | ram[h + 4] << 8
        nparts = ram[h + 5]
        parts = []
        verts, edges = [], []
        for p in range(nparts):
            q = h + 6 + 8 * p
            poff = ram[q] | ram[q + 1] << 8
            keep = list(ram[q + 2:q + 5])
            shifts = list(ram[q + 5:q + 8])
            a = base + poff
            pv, pe, pf = ram[a], ram[a + 1], ram[a + 2]
            y = a + 3
            faces_first = list(ram[y:y + pf]); y += pf
            ev1 = list(ram[y:y + pe]); y += pe
            ev2 = list(ram[y:y + pe]); y += pe
            efa = list(ram[y:y + pe]); y += pe
            efb = list(ram[y:y + pe]); y += pe
            pverts = []
            for i in range(pv):
                x, yy, z = (s8(ram[y + 3 * i + k]) << shifts[k] for k in range(3))
                pverts.append((x, yy, z))
            y += 3 * pv
            nla = list(ram[y:y + pe]); y += pe
            nlb = list(ram[y:y + pe]); y += pe
            vbase = len(verts)
            verts += pverts
            edges += [(vbase + a1, vbase + a2) for a1, a2 in zip(ev1, ev2)]
            parts.append({
                "addr": a, "vertices": pv, "edges": pe, "faces": pf, "keep": keep,
                "shifts": shifts, "end": y, "face_first": faces_first,
                "edge_faces": list(zip(efa, efb)), "next": list(zip(nla, nlb)),
            })
        shapes.append({
            "n": n, "header": h, "nv": nv, "ne": ne, "nf": nf, "extra": extra,
            "parts": parts, "verts": verts, "edges": edges,
        })
    return shapes


def draw_views(shape, size=160):
    verts, edges = shape["verts"], shape["edges"]
    img = Image.new("RGB", (size * 2, size * 2), (0, 0, 0))
    d = ImageDraw.Draw(img)
    if not verts:
        return img
    ext = max(max(abs(c) for c in v) for v in verts) or 1

    def ortho(i, j, flip_j, ox, oy, label):
        sc = (size / 2 - 10) / ext
        for a, b in edges:
            if a >= len(verts) or b >= len(verts):
                continue
            pa, pb = verts[a], verts[b]
            ya = -pa[j] if flip_j else pa[j]
            yb = -pb[j] if flip_j else pb[j]
            d.line([ox + size / 2 + pa[i] * sc, oy + size / 2 + ya * sc,
                    ox + size / 2 + pb[i] * sc, oy + size / 2 + yb * sc], fill=(200, 200, 200))
        d.text((ox + 3, oy + 2), label, fill=(120, 120, 255))

    # Views: X across with Y up (front), Z across with Y up (side), X across with Z (top).
    ortho(0, 1, True, size, 0, "front x/y")
    ortho(2, 1, True, 0, size, "side z/y")
    ortho(0, 2, False, size, size, "top x/z")
    # Perspective: yaw 30, pitch 20 degrees.
    cy, sy = math.cos(math.radians(30)), math.sin(math.radians(30))
    cp, sp = math.cos(math.radians(20)), math.sin(math.radians(20))
    pts = []
    for x, y, z in verts:
        x1, z1 = x * cy - z * sy, x * sy + z * cy
        y1, z2 = y * cp - z1 * sp, y * sp + z1 * cp
        pts.append((x1, -y1, z2))
    dist = ext * 3.5
    sc = size * 0.9

    def proj(p):
        f = dist / (dist + p[2])
        return size / 2 + p[0] * f * sc / ext / 2.2, size / 2 + p[1] * f * sc / ext / 2.2
    for a, b in edges:
        if a < len(pts) and b < len(pts):
            d.line([*proj(pts[a]), *proj(pts[b])], fill=(255, 255, 120))
    d.text((3, 2), f"#{shape['n']} v{len(verts)} e{len(edges)}", fill=(120, 255, 120))
    d.text((3, size - 12), NAMES.get(shape["n"], "(no name)")[:26], fill=(255, 160, 120))
    d.rectangle([0, 0, size * 2 - 1, size * 2 - 1], outline=(60, 60, 60))
    d.line([size, 0, size, size * 2], fill=(60, 60, 60))
    d.line([0, size, size * 2, size], fill=(60, 60, 60))
    return img


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = sys.argv[1:]

    def opt(name, default):
        return opts[opts.index(name) + 1] if name in opts else default

    ram = Path(args[0]).read_bytes()
    out = Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    base = int(opt("--base", "0900").lstrip("&$"), 16)
    count = int(opt("--count", "27"))
    prefix = opt("--prefix", "c64")
    shapes = decode(ram, base, count)
    print(" n  header  nv  ne  nf  parts  extra  shifts      extent(x,y,z)  name")
    tiles = []
    for s in shapes:
        xs = [v[0] for v in s["verts"]] or [0]
        ys = [v[1] for v in s["verts"]] or [0]
        zs = [v[2] for v in s["verts"]] or [0]
        bad = sum(1 for a, b in s["edges"] if a >= len(s["verts"]) or b >= len(s["verts"]))
        print(f"{s['n']:2d}  &{s['header']:04X}  {len(s['verts']):2d}  {len(s['edges']):2d}  {s['nf']:2d}  "
              f"{len(s['parts']):5d}  &{s['extra']:04X}  "
              f"{','.join(str(p['shifts']) for p in s['parts'])}  "
              f"x {min(xs)}..{max(xs)} y {min(ys)}..{max(ys)} z {min(zs)}..{max(zs)}"
              + f"  {NAMES.get(s['n'], '')}"
              + (f"  {bad} edges out of range" if bad else ""))
        img = draw_views(s)
        img.save(out / f"{prefix}_shape_{s['n']:02d}.png")
        tiles.append(img)
    cols = 6
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * w, (i // cols) * h))
    sheet.save(out / f"{prefix}_shapes.png")
    if "--json" in opts:
        (out / f"{prefix}_shapes.json").write_text(json.dumps(shapes, indent=1))


if __name__ == "__main__":
    main()
