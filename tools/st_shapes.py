#!/usr/bin/env python3
"""Extract and render the 3D shapes in Starglider's AUTO/STAR.PRG (Atari ST).

    st_shapes.py PRG                print the shape table (markdown)
    st_shapes.py PRG --png OUTDIR   also render every shape, every animation
                                    frame and a contact sheet
    st_shapes.py PRG --json FILE    write the shapes as JSON (vertices,
                                    edges, faces, colours, animation frames)
    --tra RESULT.TRA                draw in the flight palette, which is
                                    RESULT.TRA's (the game fades to it as
                                    play starts); without it, the start-up
                                    palette at &8E82

The format, from the renderer at &4B1C (text-segment offsets):

- &AC76: 32 words, object type -> shape number (all identity but type 6,
  which uses shape 18).
- &AF4E: the shape table, 16 bytes a shape (shape 0 is empty):
  nverts, nedges, nfaces, then offsets (from &B11E, the shape base the
  game keeps at $78(a6)) of the vertices, edges, faces and one more block
  the renderer stores but never reads, then a word (always 0).
- vertex: 8 bytes, x y z words and a pad; y is negative upwards, z away.
- edge: 4 bytes, two vertex byte offsets (index x 8).
- face: a 9-word header (+0 colour; +2 and +4 copied but never read;
  +6 negative means "always drawn"; +8 to +12 unread; +14 the vertex
  count; +16 the edge count) then the vertex indices (the first three give the
  normal, (v1-v0) x (v2-v0), visible when it points at the viewer) then
  the edge indices.
- In flight the edges of every visible face are drawn in one colour: the
  renderer loads each face's colour as it tests it and draws the edges
  afterwards, so the last face's colour wins.
- Animation (&43EE, every frame): seven frame lists; each is
  (current, last, two words, then last+1 vertex-block offsets), and the
  current one is written into its shape's vertex offset.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

TYPE_TO_SHAPE = 0xAC76
TABLE = 0xAF4E
BASE = 0xB11E
NSHAPES = 29
PALETTE = 0x8E82                # the in-game palette, 16 STF words
# (frame list, shape-table entries it drives), from &43EE
ANIMS = [(0xC17E, [7]), (0xD6CE, [10, 1]), (0xFD4C, [15]), (0xD99C, [11]),
         (0x10768, [18]), (0x11C18, [26]), (0x1204C, [27])]
# The Interrogate screen's list (&2B98 types, names via &2C4C)
INTERROGATE = 0x2B98
NAMES = 0x2C4C


def st_rgb(w):
    """An STF palette word (3 bits a gun) as 8-bit RGB."""
    return tuple(((w >> s) & 7) * 255 // 7 for s in (8, 4, 0))


def cstr(prg, a):
    out = bytearray()
    while prg.u8(a):
        out.append(prg.u8(a))
        a += 1
    return out.decode("latin-1")


def load_shapes(prg):
    shapes = []
    for k in range(NSHAPES):
        e = [prg.u16(TABLE + 16 * k + 2 * i) for i in range(8)]
        nv, ne, nf, ov, oe, of, ox, flag = e
        verts = [tuple(prg.s16(BASE + ov + 8 * i + 2 * j) for j in range(3)) for i in range(nv)]
        edges = [(prg.u16(BASE + oe + 4 * i) // 8, prg.u16(BASE + oe + 4 * i + 2) // 8) for i in range(ne)]
        faces, a = [], BASE + of
        for _ in range(nf):
            h = [prg.s16(a + 2 * j) for j in range(9)]
            nvi, nei = h[7], h[8]
            lst = [prg.s16(a + 18 + 2 * j) for j in range(nvi + nei)]
            faces.append({"colour": h[0], "always": h[3] < 0, "header": h,
                          "verts": lst[:nvi], "edges": lst[nvi:]})
            a += 18 + 2 * (nvi + nei)
        shapes.append({"index": k, "nverts": nv, "nedges": ne, "nfaces": nf,
                       "verts_at": BASE + ov, "edges_at": BASE + oe, "faces_at": BASE + of,
                       "faces_end": a, "flag": flag, "verts": verts, "edges": edges,
                       "faces": faces, "frames": [], "types": []})
    for listaddr, entries in ANIMS:
        last = prg.u16(listaddr + 2)
        offs = [prg.u16(listaddr + 8 + 2 * i) for i in range(last + 1)]
        for k in entries:
            s = shapes[k]
            s["anim_list"] = listaddr
            s["frames"] = [[tuple(prg.s16(BASE + o + 8 * i + 2 * j) for j in range(3))
                            for i in range(s["nverts"])] for o in offs]
            s["frame_offsets"] = offs
    for t in range(32):
        sh = prg.u16(TYPE_TO_SHAPE + 2 * t)
        if sh < NSHAPES:
            shapes[sh]["types"].append(t)
    names = {}
    for i in range(1, 18):
        t = prg.u16(INTERROGATE + 2 * i)
        names[t] = cstr(prg, prg.u32(NAMES + 4 * i))
    for s in shapes:
        s["names"] = [names[t] for t in s["types"] if t in names]
    return shapes


def flight_colour(s):
    return s["faces"][-1]["colour"] if s["faces"] else None


def view(verts, yaw, pitch, dist):
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    out = []
    for x, y, z in verts:
        x, z = x * cy - z * sy, x * sy + z * cy
        y, z = y * cp - z * sp, y * sp + z * cp
        out.append((x, y, z + dist))
    return out


def visible_faces(s, cam):
    vis = []
    for f in s["faces"]:
        if f["always"]:
            vis.append(True)
            continue
        v0, v1, v2 = (cam[i] for i in f["verts"][:3])
        e = [v1[i] - v0[i] for i in range(3)]
        d = [v2[i] - v0[i] for i in range(3)]
        n = (e[1] * d[2] - e[2] * d[1], e[2] * d[0] - e[0] * d[2], e[0] * d[1] - e[1] * d[0])
        vis.append(n[0] * v2[0] + n[1] * v2[1] + n[2] * v2[2] < 0)
    return vis


def render(s, verts, size, palette, yaw=0.6, pitch=0.35):
    from PIL import Image, ImageDraw
    w, h = size
    img = Image.new("RGB", (w, h), (0, 0, 0))
    if not verts:
        return img
    r = max(math.sqrt(x * x + y * y + z * z) for x, y, z in verts) or 1
    cam = view(verts, yaw, pitch, 3.2 * r)
    f = 0.9 * min(w, h) / 2 * 3.2 / 1.15
    pts = [(w / 2 + f * x / z, h / 2 + f * y / z) for x, y, z in cam]
    vis = visible_faces(s, cam)
    front = set()
    for f_, v in zip(s["faces"], vis):
        if v:
            front.update(f_["edges"])
    colour = palette[flight_colour(s) & 15] if s["faces"] else (255, 255, 255)
    d = ImageDraw.Draw(img)
    for i, (a, b) in enumerate(s["edges"]):
        if i not in front:
            d.line([pts[a], pts[b]], fill=(70, 70, 70), width=1)
    for i, (a, b) in enumerate(s["edges"]):
        if i in front:
            d.line([pts[a], pts[b]], fill=colour, width=1)
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("--png")
    ap.add_argument("--json")
    ap.add_argument("--tra")
    args = ap.parse_args()
    prg = st_prg.load(args.prg)
    shapes = load_shapes(prg)
    if args.tra:
        raw = Path(args.tra).read_bytes()
        palette = [st_rgb(int.from_bytes(raw[0x14 + 2 * i:0x16 + 2 * i], "big")) for i in range(16)]
    else:
        palette = [st_rgb(prg.u16(PALETTE + 2 * i)) for i in range(16)]

    print("| Shape | Types | Name | Verts | Edges | Faces | Face colours | Drawn in | Always-drawn faces | Frames | Data |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in shapes:
        cols = sorted({f["colour"] for f in s["faces"]})
        always = sum(f["always"] for f in s["faces"])
        span = f"&{s['verts_at']:05X}-&{s['faces_end']:05X}" if s["nverts"] else ""
        frames = len(s["frames"]) or ""
        print(f"| {s['index']} | {','.join(map(str, s['types']))} | {'; '.join(s['names'])} | {s['nverts']} | "
              f"{s['nedges']} | {s['nfaces']} | {','.join(map(str, cols))} | {flight_colour(s) if s['faces'] else ''} | "
              f"{always or ''} | {frames} | {span} |")

    if args.json:
        Path(args.json).write_text(json.dumps({"palette": palette, "shapes": shapes}, indent=1))

    if args.png:
        from PIL import Image, ImageDraw
        out = Path(args.png)
        out.mkdir(parents=True, exist_ok=True)
        cells = []
        for s in shapes[1:]:
            img = render(s, s["verts"], (320, 240), palette)
            ImageDraw.Draw(img).text((4, 4), f"shape {s['index']}: {'; '.join(s['names'])}", fill=(200, 200, 200))
            img.save(out / f"shape{s['index']:02d}.png")
            cells.append(img)
            if s["frames"]:
                n = len(s["frames"])
                cols = min(n, 8)
                rows = (n + cols - 1) // cols
                strip = Image.new("RGB", (160 * cols, 120 * rows))
                for i, fv in enumerate(s["frames"]):
                    fi = render(s, fv, (160, 120), palette)
                    ImageDraw.Draw(fi).text((2, 2), str(i), fill=(160, 160, 160))
                    strip.paste(fi, (160 * (i % cols), 120 * (i // cols)))
                strip.save(out / f"shape{s['index']:02d}_frames.png")
        cols = 7
        rows = (len(cells) + cols - 1) // cols
        sheet = Image.new("RGB", (160 * cols, 120 * rows))
        for i, c in enumerate(cells):
            sheet.paste(c.resize((160, 120)), (160 * (i % cols), 120 * (i // cols)))
        sheet.save(out / "shapes_sheet.png")


if __name__ == "__main__":
    main()
