#!/usr/bin/env python3
"""Resume the frozen C64 Starglider on py65 and profile it.

    c64_run.py IMAGE.d64 OUTDIR [--flips N] [--from F] [--script STEPS] [--shots K] [--coverage]

It rebuilds the machine with c64_unfreeze.py, then runs the game with a small
C64 model:
  - CIA1 timers A and B (B counting A's underflows) raise the IRQ as the game
    programmed them; the ICR read clears it. CIA2 stays masked, as the game
    leaves it.
  - VIC bad lines stall the CPU 40 cycles on each of the 25 bad lines of a
    312-line, 63-cycle PAL frame while the display is on, so "wall" cycles run
    ahead of CPU cycles as they do on the machine.
  - The keyboard and joysticks read as idle unless --script presses something:
    STEPS is comma-separated "flip:joy=BITS" or "flip:key=COL.ROW" items, e.g.
    "50:joy=1e,80:joy=1f" (port 2 joystick: bit 0 up, 1 down, 2 left,
    3 right, 4 fire; a clear bit is pressed, so 1f is idle).
  - &D41B (SID voice 3 oscillator) reads as a pseudo-random byte.
The game's buffer flip is the routine at &5291 (it swaps &DD00's bank and
clears the new back buffer). Each call ends a frame. The report gives:
  - wall cycles per frame, and in PAL frames (19,656 cycles each);
  - per subroutine (JSR target, innermost first), self and inclusive CPU cycles
    per frame, and the bytes it wrote to the two bitmaps;
  - the line drawer's lines, pixels (one bitmap write each) and cycles;
  - --from F counts only frames from flip F on; --shots K saves the shown
    buffer as a PNG every K flips; --coverage writes OUTDIR/coverage.txt,
    the executed address ranges (instruction starts, whole run).
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c64_unfreeze import C64Mem, unfreeze  # noqa: E402
import c64_screen  # noqa: E402

PAL_FRAME = 312 * 63
FLIP = 0x5291
LINE_ROUTINES = (0x420F, 0x4221)


class Machine(C64Mem):
    def __init__(self):
        super().__init__()
        self.wall = 0
        self.ta = self.tb = 0
        self.ta_latch = self.tb_latch = 0xFFFF
        self.cra = self.crb = 0
        self.icr_mask = 0
        self.icr_data = 0
        self.joy2 = 0x1F
        self.keys = set()  # (column, row) pressed
        self.rng = 0x1234
        self.writer = None  # routine charged with bitmap writes
        self.bitmap_writes = Counter()
        self.port_a = 0xFF

    # --- I/O reads and writes --------------------------------------------
    def __getitem__(self, a):
        if isinstance(a, slice):
            return super().__getitem__(a)
        if 0xD000 <= a < 0xE000 and self._cfg()[2]:
            if a == 0xDC0D:
                v = self.icr_data | (0x80 if self.icr_data & self.icr_mask else 0)
                self.icr_data = 0
                return v
            if a == 0xDC04:
                return self.ta & 255
            if a == 0xDC05:
                return self.ta >> 8
            if a == 0xDC00:
                return 0xE0 | self.joy2
            if a == 0xDC01:
                v = 0xFF
                for col, row in self.keys:
                    if not self.port_a & (1 << col):
                        v &= ~(1 << row)
                return v
            if a == 0xD012:
                return (self.wall % PAL_FRAME // 63) & 255
            if a == 0xD011:
                line = self.wall % PAL_FRAME // 63
                return (self.io.get(0xD011, 0x1B) & 0x7F) | (0x80 if line > 255 else 0)
            if a == 0xD41B:
                self.rng = (self.rng * 1103515245 + 12345) & 0x7FFFFFFF
                return self.rng >> 16 & 255
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if 0xD000 <= a < 0xE000 and self._cfg()[2]:
            if a == 0xDC0D:
                if v & 0x80:
                    self.icr_mask |= v & 0x1F
                else:
                    self.icr_mask &= ~v & 0x1F
                return
            if a == 0xDC04:
                self.ta_latch = (self.ta_latch & 0xFF00) | v
            elif a == 0xDC05:
                self.ta_latch = (self.ta_latch & 0xFF) | v << 8
                if not self.cra & 1:
                    self.ta = self.ta_latch
            elif a == 0xDC06:
                self.tb_latch = (self.tb_latch & 0xFF00) | v
            elif a == 0xDC07:
                self.tb_latch = (self.tb_latch & 0xFF) | v << 8
                if not self.crb & 1:
                    self.tb = self.tb_latch
            elif a == 0xDC0E:
                self.cra = v
                if v & 0x10:
                    self.ta = self.ta_latch
            elif a == 0xDC0F:
                self.crb = v
                if v & 0x10:
                    self.tb = self.tb_latch
            elif a == 0xDC00:
                self.port_a = v
        elif self.writer is not None and (0xA000 <= a < 0xBF40 or 0xE000 <= a < 0xFF40):
            self.bitmap_writes[self.writer] += 1
        super().__setitem__(a, v)

    # --- time -------------------------------------------------------------
    def tick(self, cycles):
        """Advance by CPU cycles; returns the wall cycles including bad lines."""
        start = self.wall
        end = start + cycles
        # Bad lines: raster lines 48-247 with (line & 7) == YSCROLL, display on.
        d011 = self.io.get(0xD011, 0x1B)
        if d011 & 0x10:
            ys = d011 & 7
            f0, f1 = start // 63, end // 63
            for line_abs in range(f0 + 1, f1 + 1):
                line = line_abs % 312
                if 48 <= line <= 247 and (line & 7) == ys:
                    end += 40
        self.wall = end
        elapsed = end - start
        # CIA1 timers.
        if self.cra & 1:
            self.ta -= elapsed
            while self.ta < 0:
                self.ta += self.ta_latch + 1
                self.icr_data |= 1
                if self.crb & 1 and (self.crb & 0x60) == 0x40:
                    self.tb -= 1
                    if self.tb < 0:
                        self.tb = self.tb_latch
                        self.icr_data |= 2
        if self.crb & 1 and (self.crb & 0x60) == 0:
            self.tb -= elapsed
            while self.tb < 0:
                self.tb += self.tb_latch + 1
                self.icr_data |= 2
        return elapsed

    def irq_line(self):
        return bool(self.icr_data & self.icr_mask)


def parse_script(text):
    steps = defaultdict(list)
    for item in filter(None, (text or "").split(",")):
        when, what = item.split(":")
        k, v = what.split("=")
        steps[int(when)].append((k, v))
    return steps


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = sys.argv[1:]

    def opt(name, default):
        return opts[opts.index(name) + 1] if name in opts else default

    flips_wanted = int(opt("--flips", "100"))
    start_flip = int(opt("--from", "1"))
    shots = int(opt("--shots", "0"))
    script = parse_script(opt("--script", ""))
    out = Path(args[1])
    out.mkdir(parents=True, exist_ok=True)

    m = Machine()
    mem, mpu, _ = unfreeze(args[0], m)
    # Carry the frozen I/O state into the model.
    io = dict(m.io)
    m.ta_latch = io.get(0xDC04, 0) | io.get(0xDC05, 0) << 8
    m.tb_latch = io.get(0xDC06, 0) | io.get(0xDC07, 0) << 8
    m.ta, m.tb = m.ta_latch, m.tb_latch
    m.cra, m.crb = io.get(0xDC0E, 0), io.get(0xDC0F, 0)
    m.icr_mask = 0x02  # the game's own set-up at &631A writes &82
    m.icr_data = 0

    self_cyc = Counter()
    incl_cyc = Counter()
    edge_cyc = Counter()
    edge_calls = Counter()
    calls = Counter()
    stack = []  # (target, sp_after_push, cpu_cycles_at_entry)
    flips = []
    flip_count = 0
    cpu_total = 0
    routine = "resume"
    counting = False
    line_frame = [0, 0]  # calls, pixels in the frame being drawn
    per_frame = []  # (flip, line calls, line pixels)
    executed = bytearray(0x10000)
    while flip_count < flips_wanted:
        pc = mpu.pc
        executed[pc] = 1
        if pc == FLIP:
            flip_count += 1
            if flip_count >= start_flip:
                flips.append((m.wall, cpu_total))
                per_frame.append((flip_count, *line_frame))
            counting = flip_count >= start_flip
            line_frame = [0, 0]
            m.writer = None
            for k, v in script.get(flip_count, []):
                if k == "joy":
                    m.joy2 = int(v, 16)
                elif k == "key":
                    col, row = map(int, v.split("."))
                    m.keys ^= {(col, row)}
            if shots and flip_count % shots == 0:
                shown = 0xE000 if m.ram[0x98] == 0xE0 else 0xA000  # before the swap
                screen = 0xCC00 if shown == 0xE000 else 0x8C00
                img = c64_screen.render(m.ram, m.colour, shown, screen, True, 0)
                img.resize((640, 400)).save(out / f"flip{flip_count:04d}.png")
        if m.irq_line() and not mpu.p & mpu.INTERRUPT:
            stack.append(("IRQ", mpu.sp - 3, cpu_total))
            calls["IRQ"] += counting

            before = mpu.processorCycles
            mpu.irq()
            c = mpu.processorCycles - before
            cpu_total += c
            m.tick(c)
            continue
        op = m.ram[pc] if pc < 0xD000 or pc >= 0xE000 else 0
        routine = stack[-1][0] if stack else "top"
        m.writer = routine if counting else None
        before_writes = m.bitmap_writes[routine]
        before = mpu.processorCycles
        mpu.step()
        c = mpu.processorCycles - before
        cpu_total += c
        m.tick(c)
        if routine in LINE_ROUTINES:
            line_frame[1] += m.bitmap_writes[routine] - before_writes
        if counting:
            self_cyc[routine] += c
        if op == 0x20:  # JSR
            target = mpu.pc
            stack.append((target, mpu.sp, cpu_total - c))
            if counting:
                calls[target] += 1
            if target in LINE_ROUTINES:
                line_frame[0] += 1
        elif op in (0x60, 0x40):  # RTS, RTI
            while stack and stack[-1][1] < mpu.sp:
                t, _sp, entry = stack.pop()
                if counting:
                    incl_cyc[t] += cpu_total - entry
                    parent = stack[-1][0] if stack else "top"
                    edge_cyc[(parent, t)] += cpu_total - entry
                    edge_calls[(parent, t)] += 1
    nframes = len(flips) - 1
    lines = []
    if nframes > 0:
        walls = [flips[i + 1][0] - flips[i][0] for i in range(nframes)]
        cpus = [flips[i + 1][1] - flips[i][1] for i in range(nframes)]
        mean_wall = sum(walls) / nframes
        lines.append(f"{nframes} frames (flip to flip): wall cycles mean {mean_wall:.0f}, "
                     f"min {min(walls)}, max {max(walls)}; "
                     f"{mean_wall / PAL_FRAME:.2f} PAL frames each, "
                     f"{50 * PAL_FRAME / mean_wall:.1f} frames/s at 50Hz")
        lines.append(f"CPU cycles per frame mean {sum(cpus) / nframes:.0f}")
        lines.append("per-frame wall cycles: " + " ".join(map(str, walls)))
        lc = sum(f[1] for f in per_frame[1:])
        lp = sum(f[2] for f in per_frame[1:])
        lcyc = sum(incl_cyc[r] for r in LINE_ROUTINES)
        lines.append(f"line drawer (&420F/&4221): {lc / nframes:.1f} lines and {lp / nframes:.0f} pixels "
                     f"per frame, {lcyc / nframes:.0f} cycles per frame"
                     + (f", {lcyc / lp:.1f} cycles per pixel including set-up, "
                        f"{lp / max(lc, 1):.1f} pixels per line" if lp else ""))
        lines.append("per frame (flip: lines/pixels/wall cycles): " + " ".join(
            f"{per_frame[i + 1][0]}:{per_frame[i + 1][1]}/{per_frame[i + 1][2]}/{walls[i]}"
            for i in range(nframes)))
    total_cpu = max(sum(self_cyc.values()), 1)
    lines.append("")
    lines.append("routine   calls   self/frame  incl/frame  self%   bitmap writes/frame")
    nf = max(nframes, 1)
    for r, c in self_cyc.most_common(45):
        name = r if isinstance(r, str) else f"&{r:04X}"
        lines.append(f"{name:>7} {calls[r]:7d} {c / nf:11.0f} {incl_cyc[r] / nf:11.0f} "
                     f"{100 * c / total_cpu:6.1f} {m.bitmap_writes[r] / nf:10.0f}")
    lines.append("")
    lines.append("call tree (inclusive CPU cycles per frame, calls per frame; children over 300 cycles)")
    children = defaultdict(list)
    for (par, ch), c in edge_cyc.items():
        children[par].append((c, ch))

    def nm(r):
        return r if isinstance(r, str) else f"&{r:04X}"

    def tree(node, depth, seen):
        for c, ch in sorted(children.get(node, []), reverse=True):
            if c / nf < 300 or ch in seen:
                continue
            lines.append(f"{'  ' * depth}{nm(ch)}  {c / nf:.0f}  x{edge_calls[(node, ch)] / nf:.1f}")
            tree(ch, depth + 1, seen | {ch})

    tree("top", 0, set())
    report = "\n".join(lines)
    (out / "profile.txt").write_text(report + "\n")
    print(report)
    if "--coverage" in opts:
        ranges, start, last = [], None, None
        for a in range(0x10000):
            if executed[a]:
                if start is None or a - last > 16:
                    if start is not None:
                        ranges.append((start, last))
                    start = a
                last = a
        if start is not None:
            ranges.append((start, last))
        (out / "coverage.txt").write_text("".join(
            f"&{a:04X}-&{b:04X}\n" for a, b in ranges))
    (out / "ram_end.bin").write_bytes(bytes(m.ram))
    (out / "colour_end.bin").write_bytes(bytes(m.colour[:1000]))


if __name__ == "__main__":
    main()
