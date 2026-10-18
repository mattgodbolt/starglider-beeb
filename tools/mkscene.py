#!/usr/bin/env python3
"""Scenes captured from the ST (tools/st_scenes.py) as the port's inputs,
with what the ST's renderer makes of them (tools/st_render.py), for
tools/scenerun.mjs and tools/scenecheck.py.

    mkscene.py PRG SCENES.json OUT.json [--frames A-B]

Each frame becomes:

- `objects`: the objects' bank, every slot as the port keeps it (the ST's
  64-byte record at its own offsets, its words little-endian; the bytes at
  +22 to +25 as they are), the ST's 140 slots then the silo's tunnel
  (&1218) and missile (&1258);
- `zp`: the frame's inputs, by symbol: the player, the slot count, the
  docked and silo-missile flags, the all-faces flag, the beam's colour,
  and the missile view's flag, the missile's place and angles and the
  window's step (in the missile view its camera is the missile's);
- `anim`: each shape's animation frame, the index into its list of the
  vertex block the ST's shape table names;
- `expect`: the ST's coarse, near and draw lists (slots, in the order
  pushed), each rotated object's camera-space position, and each drawn
  object's lines by edge.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402
import st_render as R  # noqa: E402
import st_shapes  # noqa: E402

SLOTS = 140
TUNNEL, MISSILE = 0x1218, 0x1258
BYTE_FIELDS = range(0x22, 0x26)


def slot_of(a):
    if a == TUNNEL:
        return SLOTS
    if a == MISSILE:
        return SLOTS + 1
    i, r = divmod(a - (R.A6 + R.OBJECTS), R.OBJECT_SIZE)
    assert r == 0 and 0 <= i < SLOTS, hex(a)
    return i


def record(mem, a):
    out = bytearray(mem.u8(a + i) for i in range(R.OBJECT_SIZE))
    for i in range(0, R.OBJECT_SIZE, 2):
        if i not in BYTE_FIELDS:
            out[i], out[i + 1] = out[i + 1], out[i]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("scenes")
    ap.add_argument("out")
    ap.add_argument("--frames")
    args = ap.parse_args()
    prg = st_prg.load(args.prg)
    shapes = st_shapes.load_shapes(prg)
    data = json.loads(Path(args.scenes).read_text())
    frames = data["frames"]
    if args.frames:
        a, b = args.frames.split("-")
        frames = frames[int(a):int(b) + 1]
    model = R.Renderer(prg)
    out = []
    for fr in frames:
        mem = R.Memory(fr, data["regions"])
        objects = bytearray()
        for i in range(SLOTS):
            objects += record(mem, R.A6 + R.OBJECTS + R.OBJECT_SIZE * i)
        objects += record(mem, TUNNEL) + record(mem, MISSILE)
        zp = {
            "pl_x": mem.var(0x12E), "pl_y": mem.var(0x130), "pl_z": mem.var(0x132),
            "pl_pitch": mem.var(0x13A), "pl_heading": mem.var(0x13C), "pl_roll": mem.var(0x13E),
            "n_slots": mem.var(0x1D8),
            "docked": mem.u8(R.A6 + 0x2CA),
            # the docked list reads it, through the silo's pointer ($A8)
            "silo_missile": 1 if mem.u8(R.A6 + 0x2CA) and mem.u8(mem.u32(R.A6 + 0xA8) + 0x14) else 0,
            "all_faces": 0x80 if mem.u8(R.A6 + 0x2BD) else 0,
            # (captures before the beam's colour was dumped draw it in 15)
            "beam_colour": mem.u16(R.BASE + 0x0D97E) & 15 if mem.has(R.BASE + 0x0D97E) else 15,
            # the missile view (L_05248): its camera, and its window's step
            "mv_render": mem.u8(R.A6 + 0x2C9),
            "m_x": mem.var(0x26A), "m_y": mem.var(0x26C), "m_z": mem.var(0x26E),
            "m_pitch": mem.var(0x270), "m_heading": mem.var(0x272), "m_roll": mem.var(0x274),
            "m_iris": mem.var(0x27C),
        }
        anim = []
        for s in shapes:
            cur = mem.u16(R.BASE + R.SHAPE_TABLE + 16 * s["index"] + 6) if s["index"] else 0
            offs = s.get("frame_offsets")
            anim.append(offs.index(cur) if offs and cur in offs else 0)
        result = model.frame(mem)
        expect = {
            "coarse": [slot_of(a) for a in result["coarse"]],
            "near": [slot_of(a) for a in result["near"]],
            "draw": [slot_of(a) for a in result["draw"]],
            "rel": {slot_of(a): v for a, v in result["rel"].items()},
            "objects": [{"slot": slot_of(o["object"]), "exploding": o["exploding"], "lines": o["lines"],
                         "edges": o["edges"]} for o in result["objects"]],
        }
        out.append({"vbl": fr["vbl"], "segment": fr["segment"], "objects": objects.hex(), "zp": zp,
                    "anim": anim, "expect": expect})
    Path(args.out).write_text(json.dumps({"frames": out}))
    print(f"{args.out}: {len(out)} frames")


if __name__ == "__main__":
    main()
