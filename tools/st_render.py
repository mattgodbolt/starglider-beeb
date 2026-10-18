#!/usr/bin/env python3
"""A model of Starglider's (Atari ST) renderer, exact to the 68000's
arithmetic, checked against the lines the ST drew (tools/st_scenes.py).

    st_render.py PRG SCENES.json [--frames A-B] [--show N]

For each captured frame it rebuilds, from the frame's dumped state, what
world_render does: the camera matrix from the player's angles (&050A2,
&04258), the coarse and near lists (&05750), each object rotated into
camera space and the draw list (&057B8, &04092), then each drawn object
(&04B1C): its matrix (&04114), the back-face test (&04BC2), the vertex
transform (&03FFE), the near-plane clip (&0A374), the projection (&04D66)
and the clip to the window (&0A170). It checks the camera-space positions
and the lists against the frame's own, and every object's lines against
the lines the ST drew for it, and prints what differs.

The 68000's semantics that matter, all kept:

- a fixed-point product is `muls`, `asl.l #2`, `swap`: the high word of
  the 32-bit product shifted left 2, so floor(a * b / 16384) wrapped to 16
  bits;
- `divs` truncates towards zero and, when the quotient doesn't fit 16
  bits, leaves its destination as it was (V set), which the code then
  uses;
- word arithmetic wraps at 16 bits;
- the back-face test multiplies the cross product's 32-bit components by
  `muls.w`, which takes only their low words.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

BASE = 0x109BE
A6 = 0x5BF00
TYPE_TO_SHAPE = 0x0AC76
SIZE_Z = 0x0ACB6                    # per type: the draw list's "wholly behind" test
SHAPE_TABLE = 0x0AF4E
SHAPE_BASE = 0x0B11E                # $78(a6)
SINE = 0x13D6C                      # $6C(a6); cosine ($70) is 1024 entries on
OBJECTS = 0x129A                    # (a6)
OBJECT_SIZE = 0x40


def w(x):
    """A 68000 word: wrap to signed 16 bits."""
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def lng(x):
    """A 68000 long: wrap to signed 32 bits."""
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def muls(a, b):
    return w(a) * w(b)


def fmul(a, b):
    """muls.w; asl.l #2; swap: the high word of the product shifted left 2."""
    return w(lng(muls(a, b) << 2) >> 16)


def divs(dividend, divisor):
    """divs.w: the quotient, truncated towards zero, or None on overflow."""
    dividend, divisor = lng(dividend), w(divisor)
    q = abs(dividend) // abs(divisor)
    if (dividend < 0) != (divisor < 0):
        q = -q
    return q if -0x8000 <= q <= 0x7FFF else None


class Memory:
    """A frame's dumped regions, addressed as the ST addresses them."""

    def __init__(self, frame, regions):
        self.blocks = [(addr, bytes.fromhex(frame["memory"][name])) for name, addr, _ in regions]

    def has(self, a):
        return any(start <= a < start + len(data) for start, data in self.blocks)

    def u8(self, a):
        for start, data in self.blocks:
            if start <= a < start + len(data):
                return data[a - start]
        raise KeyError(f"&{a:X} not dumped")

    def u16(self, a):
        return (self.u8(a) << 8) | self.u8(a + 1)

    def s16(self, a):
        return w(self.u16(a))

    def u32(self, a):
        return (self.u16(a) << 16) | self.u16(a + 2)

    def var(self, off):
        return self.s16(A6 + off)


class Renderer:
    def __init__(self, prg):
        self.prg = prg
        self.sine = [prg.s16(SINE + 2 * i) for i in range(6145)]
        self.table = {}                 # $2F8(a6): transformed vertices, kept between objects
        self.cache = None               # the angles build_object_matrix last built for
        self.m = None

    def sincos(self, index):
        return self.sine[index], self.sine[index + 1024]

    def angles(self, pitch, heading, roll):
        """The six sines world_render and build_object_matrix look up."""
        s1, c1 = self.sincos(pitch & 0xFFF)
        s2, c2 = self.sincos(heading & 0xFFF)
        s3, c3 = self.sincos((roll & 0x1FF) * 8)
        return s1, c1, s2, c2, s3, c3

    @staticmethod
    def matrix(s1, c1, s2, c2, s3, c3):
        """&04190 / &04258: nine 2.14 words, as rows (x', y', z') of
        coefficients on (x, y, z)."""
        d6 = fmul(s3, s1)
        d7 = fmul(c2, c3)
        m156 = w(d7 + fmul(s2, d6))
        m158 = w(fmul(fmul(s1, s2), c3) - fmul(s3, c2))
        m15a = fmul(s2, c1)
        m15c = fmul(c1, s3)
        m15e = fmul(c1, c3)
        m160 = w(-s1)
        m162 = w(fmul(d6, c2) - fmul(s2, c3))
        m164 = w(fmul(s3, s2) + fmul(d7, s1))
        m166 = fmul(c1, c2)
        return ((m156, m15c, m162), (m158, m15e, m164), (m15a, m160, m166))

    @staticmethod
    def rotate(m, x, y, z):
        """&04092 (camera) and the products of &03FFE."""
        return tuple(w(fmul(r[0], x) + fmul(r[1], y) + fmul(r[2], z)) for r in m)

    def transform(self, x, y, z):
        """&03FFE: the object's matrix, >> 4, plus its camera-space position."""
        rx, ry, rz = self.rotate(self.m, x, y, z)
        return (w((rx >> 4) + self.pos[0]), w((ry >> 4) + self.pos[1]), w((rz >> 4) + self.pos[2]))

    # ---- the frame ---------------------------------------------------------------
    def frame(self, mem):
        """Everything world_render computes before drawing, and the lines."""
        self.mem = mem
        pitch, heading, roll = mem.var(0x13A), mem.var(0x13C), mem.var(0x13E)
        self.camera = self.matrix(*self.angles(pitch, heading, w(-roll)))
        player = (mem.var(0x12E), mem.var(0x130), mem.var(0x132))
        coarse = self.coarse_list(player)
        near, drawlist, rel = self.lists(coarse, player)
        objects = []
        for a in reversed(drawlist):            # world_render reads the list from its top
            if mem.s16(a) == 0:
                continue
            exploding = mem.u8(a + 0x24) != 0
            self.line_edges = []
            lines = [] if exploding else self.draw_shape(a, rel[a], pitch, heading, roll)
            objects.append({"object": a, "exploding": exploding, "lines": lines, "edges": self.line_edges})
        return {"coarse": coarse, "near": near, "draw": drawlist, "rel": rel, "objects": objects}

    def coarse_list(self, player):
        """&05750: every object near the player in z, or in x when it's far
        behind in z (the test as it is, not a box). Pushed in slot order.
        Docked (&05672), it's the tunnel and, while it's there, the silo's
        missile."""
        mem, out = self.mem, []
        if mem.u8(A6 + 0x2CA):
            out = [0x1218]
            if mem.u8(mem.u32(A6 + 0xA8) + 0x14):
                out.append(0x1258)
            return out
        count = mem.var(0x1D8)
        for i in range(count):
            a = A6 + OBJECTS + OBJECT_SIZE * i
            if mem.s16(a) == 0:
                continue
            dx = w(mem.s16(a + 4) - player[0])
            dz = w(mem.s16(a + 8) - player[2])
            if dz > 0x2020:
                continue
            if dz <= w(0xDFE0) and not (w(0xDFE0) <= dx <= 0x2020):
                continue
            out.append(a)
        return out

    def lists(self, coarse, player):
        """&057B8: each coarse object rotated into camera space; the near
        list (not exploding) and the draw list (in front, in the view's
        pyramid), both pushed in the order read, the coarse list's top
        first."""
        mem = self.mem
        near, drawlist, rel = [], [], {}
        for a in reversed(coarse):
            t = mem.s16(a)
            if t == 0:
                continue
            d = (w(mem.s16(a + 4) - player[0]), w(mem.s16(a + 6) - player[1]), w(mem.s16(a + 8) - player[2]))
            x, y, z = self.rotate(self.camera, *d)
            rel[a] = (x, y, z)
            if mem.u8(a + 0x24) == 0:
                near.append(a)
            if z > 0x2000:
                continue
            if z <= w(-self.prg.s16(SIZE_Z + 2 * t)):
                continue
            z2 = w(z + z)
            if not (w(-z2) <= x <= z2 and w(-z2) <= y <= z2):
                continue
            drawlist.append(a)
        return near, drawlist, rel

    # ---- an object ---------------------------------------------------------------
    def draw_shape(self, a, pos, pitch, heading, roll):
        mem, prg = self.mem, self.prg
        t = mem.s16(a)
        shape = prg.u16(TYPE_TO_SHAPE + 2 * t)
        e = SHAPE_TABLE + 16 * shape
        nv, ne, nf = mem.u16(BASE + e), mem.u16(BASE + e + 2), mem.u16(BASE + e + 4)
        verts = SHAPE_BASE + mem.u16(BASE + e + 6)      # the animations write this one
        edges = SHAPE_BASE + prg.u16(e + 8)
        faces = SHAPE_BASE + prg.u16(e + 10)
        self.pos = pos
        ang = (w(mem.s16(a + 0x0A) + pitch), w(mem.s16(a + 0x0C) + heading), w(-roll))
        if ang != self.cache:                           # &04114 keeps the last matrix
            self.cache = ang
            self.m = self.matrix(*self.angles(*ang))
        # Marks by index; a face may name an index past the shape's count,
        # which marks a byte nothing reads.
        vmark = [0] * 256
        emark = [0] * 256
        vert = lambda i: tuple(prg.s16(verts + 8 * i + 2 * j) for j in range(3))
        always = mem.u8(A6 + 0x2BD) != 0

        def test_vertex(i):                             # &04320
            if vmark[i] > 0:
                return self.table[i]
            vmark[i] = 1
            self.table[i] = self.transform(*vert(i))
            return self.table[i]

        f = faces
        colour = 0
        for _ in range(nf):
            hdr = [prg.s16(f + 2 * j) for j in range(9)]
            colour = hdr[0] & 0xFFFF                    # $208: the last face's wins
            if mem.has(BASE + f - 18):                  # the beam's, which animate_shapes cycles
                colour = mem.u16(BASE + f - 18)
            f += 18
            nvi, nei = hdr[7], hdr[8]
            idx = [prg.s16(f + 2 * j) for j in range(nvi + nei)]
            visible = always or hdr[3] < 0
            if not visible:
                v0 = [c >> 2 for c in test_vertex(idx[0])]
                v1 = [c >> 2 for c in test_vertex(idx[1])]
                v2 = [c >> 2 for c in test_vertex(idx[2])]
                e1 = [w(v1[k] - v0[k]) for k in range(3)]
                e2 = [w(v2[k] - v0[k]) for k in range(3)]
                n0 = lng(muls(e2[2], e1[1]) - muls(e2[1], e1[2]))
                n1 = lng(muls(e2[0], e1[2]) - muls(e2[2], e1[0]))
                n2 = lng(muls(e2[1], e1[0]) - muls(e2[0], e1[1]))
                dot = lng(muls(n0, v2[0]) + muls(n1, v2[1]) + muls(n2, v2[2]))
                visible = dot < 0
            if visible:
                for i in idx[:nvi]:
                    vmark[i] = -1
                for i in idx[nvi:]:
                    emark[i] = -1
            f += 2 * (nvi + nei)
        for i in range(nv):                             # &04CD8
            if vmark[i] < 0:
                self.table[i] = self.transform(*vert(i))
                vmark[i] = 1
        lines = []
        self.line_edges = []                            # each line's edge number
        for i in range(ne):                             # &04D16
            if emark[i]:
                p = self.table.get(prg.u16(edges + 4 * i) // 8, (0, 0, 0))
                q = self.table.get(prg.u16(edges + 4 * i + 2) // 8, (0, 0, 0))
                line = self.edge(p, q)
                if line:
                    lines.append(line + [colour])
                    self.line_edges.append(i)
        return lines

    def edge(self, p, q):
        """&04D66: clip at z = 2, project, clip to the window."""
        r = self.clip_near(list(p), list(q))
        if r is None:
            return None
        (x0, y0, z0), (x1, y1, z1) = r
        shift = self.mem.var(0x212)
        cx, cy = self.mem.var(0x1FC), self.mem.var(0x1FE)

        def project(v, z):
            n = lng(v << shift)
            q = divs(n, z)
            return w(n if q is None else q)

        line = [w(project(x0, z0) + cx), w(project(y0, z0) + cy),
                w(project(x1, z1) + cx), w(project(y1, z1) + cy)]
        return self.clip_2d(line)

    @staticmethod
    def clip_near(p, q):
        """&0A374: the side planes are jumped over; only z < 2 is clipped,
        by its own arithmetic: the fraction is (2 - z0) / (z1 - z0) as a
        16-bit quotient of (2 - z0) << 16, used as if it had 15 bits, and
        on overflow (a fraction of a half or more) the point stays put."""
        while True:
            c0, c1 = p[2] < 2, q[2] < 2
            if not c0 and not c1:
                return p, q
            if c0 and c1:
                return None
            if not c0:
                p, q = q, p                             # &0A516, and it stays swapped
                continue
            frac = divs(((2 - p[2]) & 0xFFFF) << 16, w(q[2] - p[2]))
            frac = 0 if frac is None else frac          # overflow: d0's low word is 0
            for k in (0, 1):
                p[k] = w(p[k] + w(lng(muls(w(q[k] - p[k]), frac) << 1) >> 16))
            p[2] = 2

    def clip_2d(self, line):
        """&0A170: Cohen-Sutherland to the window $146-$14C."""
        xmin, xmax = self.mem.var(0x146), self.mem.var(0x148)
        ymin, ymax = self.mem.var(0x14A), self.mem.var(0x14C)
        x0, y0, x1, y1 = line

        def code(x, y):
            return (8 if x > xmax else 0) | (4 if y > ymax else 0) | (2 if x < xmin else 0) | (1 if y < ymin else 0)

        def cut(a, b, c, d):
            """a + (b * c) / d, as muls then divs into a word add."""
            prod = muls(b, c)
            q = divs(prod, d)
            return w(a + (prod if q is None else q))

        while True:
            c0, c1 = code(x0, y0), code(x1, y1)
            if not (c0 | c1):
                return [x0, y0, x1, y1]
            if c0 & c1:
                return None
            if x1 == x0:                                # &0A2F8: vertical
                y0 = min(max(y0, ymin), ymax) if (y0 < ymin or y0 > ymax) else y0
                y1 = min(max(y1, ymin), ymax) if (y1 < ymin or y1 > ymax) else y1
                continue
            if y1 == y0:                                # &0A330: horizontal
                x0 = min(max(x0, xmin), xmax) if (x0 < xmin or x0 > xmax) else x0
                x1 = min(max(x1, xmin), xmax) if (x1 < xmin or x1 > xmax) else x1
                continue
            if c0 == 0:
                if c1 == 0:
                    continue
                x0, y0, x1, y1 = x1, y1, x0, y0         # &0A268, kept swapped
                c0, c1 = c1, c0
            if c0 & 1:
                x0, y0 = cut(x0, w(ymin - y0), w(x1 - x0), w(y1 - y0)), ymin
            elif c0 & 2:
                x0, y0 = xmin, cut(y0, w(xmin - x0), w(y1 - y0), w(x1 - x0))
            elif c0 & 4:
                x0, y0 = cut(x0, w(ymax - y0), w(x1 - x0), w(y1 - y0)), ymax
            else:
                x0, y0 = xmax, cut(y0, w(xmax - x0), w(y1 - y0), w(x1 - x0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("scenes")
    ap.add_argument("--frames", default=None, help="A-B, the frames to check")
    ap.add_argument("--show", type=int, default=3, help="differences to print")
    args = ap.parse_args()
    prg = st_prg.load(args.prg)
    data = json.loads(Path(args.scenes).read_text())
    frames = data["frames"]
    lo, hi = 0, len(frames)
    if args.frames:
        a, b = args.frames.split("-")
        lo, hi = int(a), int(b) + 1
    r = Renderer(prg)
    stats = {"frames": 0, "rel_bad": 0, "list_bad": 0, "objects": 0, "objects_bad": 0, "lines": 0}
    shown = 0
    for n in range(lo, min(hi, len(frames))):
        fr = frames[n]
        mem = Memory(fr, data["regions"])
        out = r.frame(mem)
        stats["frames"] += 1
        for a, (x, y, z) in out["rel"].items():
            got = (mem.s16(a + 0x28), mem.s16(a + 0x2A), mem.s16(a + 0x2C))
            if got != (x, y, z):
                stats["rel_bad"] += 1
                if shown < args.show:
                    shown += 1
                    print(f"frame {n}: object &{a:X} camera-space {got} on the ST, {(x, y, z)} in the model")
        if len(out["draw"]) != mem.var(0x23E) or len(out["near"]) != mem.var(0x240):
            stats["list_bad"] += 1
            if shown < args.show:
                shown += 1
                print(f"frame {n}: lists draw {mem.var(0x23E)}/{len(out['draw'])} "
                      f"near {mem.var(0x240)}/{len(out['near'])} (ST/model)")
        st_objects = [o for o in fr["drawn"] if isinstance(o["object"], int)]
        for mine, theirs in zip(out["objects"], st_objects):
            stats["objects"] += 1
            stats["lines"] += len(theirs["lines"])
            if mine["object"] != theirs["object"] or (not mine["exploding"] and mine["lines"] != theirs["lines"]):
                stats["objects_bad"] += 1
                if shown < args.show:
                    shown += 1
                    print(f"frame {n}: object &{theirs['object']:X} (type {mem.s16(theirs['object'])})")
                    print(f"  ST    {theirs['lines']}")
                    print(f"  model {mine['lines']}")
        if len(out["objects"]) != len(st_objects):
            stats["objects_bad"] += 1
    print(" ".join(f"{k} {v}" for k, v in stats.items()))
    return 1 if stats["rel_bad"] or stats["list_bad"] or stats["objects_bad"] else 0


if __name__ == "__main__":
    sys.exit(main())
