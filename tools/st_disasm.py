#!/usr/bin/env python3
"""Disassemble an Atari ST GEMDOS program (Starglider's AUTO/STAR.PRG) with
Capstone, following the code from its entry point.

    st_disasm.py PRG [--ctl FILE] [--out FILE] [--map]

Addresses are offsets into the program's text segment (the program is
loaded at base 0), written &XXXXX as in docs/research/st.md.

- The relocation table is applied, so a relocated absolute long is a text
  offset and gets a label; an absolute that is not relocated is a fixed
  ST address (hardware, system variables, or the game's own fixed RAM).
- Code is found by recursive descent from the entry (offset 0) and from
  the control file's roots, following branches, calls and static jumps.
  A pointer stored into a hardware exception vector (the CPU's, the
  autovectors and the MFP's; not the traps, which Starglider uses as
  variables), directly or through `lea X,an` then `move.l an,vector`, is a
  root too.
- Line-A words ($Axxx) are decoded as one-word `linea` instructions.
- Everything not reached is listed as data (dc.b with ASCII).
- `--map` prints the code and data ranges instead of the listing.

The control file (default tools/st_star.ctl next to this script) has one
directive per line; '&' or '$' hex, or decimal:

    c ADDR [NAME]          a code root (a routine reached only indirectly)
    l ADDR NAME            a label name (code or data)
    t ADDR COUNT w [BASE]  a jump table of COUNT word offsets, relative to
                           BASE (default the table); each entry is a root
    t ADDR COUNT l [STRIDE]  COUNT relocated longs STRIDE bytes apart
                           (default 4); each is a code root
    d ADDR END             force data (overrides code discovery)
    ; ADDR COMMENT         a comment printed before ADDR
"""
import argparse
import re
import struct
import sys
from pathlib import Path

import capstone
from capstone import m68k

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_prg  # noqa: E402

UNCOND = {"bra", "jmp", "rts", "rte", "rtr"}
CALLS = {"bsr", "jsr"}
STOPS = {"rts", "rte", "rtr", "illegal"}


def is_vector(a):
    """An exception vector the hardware uses: CPU exceptions, the
    autovectors (HBL &68, VBL &70) and the MFP's &100-&13C. The traps'
    &80-&BC are left out: Starglider keeps variables there."""
    return 8 <= a < 0x40 or 0x60 <= a < 0x80 or 0x100 <= a < 0x140


def num(s):
    s = s.strip()
    if s[0] in "&$":
        return int(s[1:], 16)
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s)


class LineA:
    """A Line-A trap word ($Axxx): TOS's graphics primitives. Capstone has
    no name for them; each is one word and execution continues after it."""
    id = 1
    size = 2
    operands = ()

    def __init__(self, address, word):
        self.address = address
        self.bytes = word
        self.mnemonic = "linea"
        self.op_str = f"#${word[1] & 0x0F:x}"


class Ctl:
    def __init__(self):
        self.roots = {}
        self.labels = {}
        self.tables = []
        self.data = []
        self.comments = {}

    @classmethod
    def read(cls, path):
        ctl = cls()
        if not path or not Path(path).exists():
            return ctl
        for line in Path(path).read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            kind, rest = line[0], line[1:].strip()
            parts = rest.split(None, 1)
            if not parts:
                continue
            addr = num(parts[0])
            arg = parts[1] if len(parts) > 1 else ""
            if kind == "c":
                ctl.roots[addr] = arg.strip() or None
                if arg.strip():
                    ctl.labels[addr] = arg.strip()
            elif kind == "l":
                ctl.labels[addr] = arg.strip()
            elif kind == "t":
                f = arg.split()
                if f[1] == "w":
                    extra = num(f[2]) if len(f) > 2 else addr
                else:
                    extra = num(f[2]) if len(f) > 2 else 4
                ctl.tables.append((addr, num(f[0]), f[1], extra))
            elif kind == "d":
                ctl.data.append((addr, num(arg)))
            elif kind == ";":
                ctl.comments.setdefault(addr, []).append(arg)
        return ctl


class Disasm:
    def __init__(self, prg, ctl):
        self.p = prg
        self.ctl = ctl
        self.n = len(prg.image)
        self.reloc = set(prg.relocs)
        self.md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)
        self.md.detail = True
        self.insn = {}          # addr -> capstone insn
        self.owner = {}         # byte offset -> insn start
        self.calls = set()      # call targets
        self.jumps = set()      # branch targets
        self.datarefs = {}      # target -> set of referencing insns
        self.indirect = []      # (addr, text) unresolved jumps
        self.forced = bytearray(self.n)
        for a, e in ctl.data:
            for k in range(a, min(e, self.n)):
                self.forced[k] = 1

    def decode(self, a):
        if a in self.insn:
            return self.insn[a]
        if a < 0 or a >= self.n or a & 1 or self.forced[a]:
            return None
        code = bytes(self.p.image[a:a + 10])
        if code[0] & 0xF0 == 0xA0:
            return LineA(a, code[:2])
        for i in self.md.disasm(code, a, 1):
            # Capstone's M68K decoder turns an illegal word into "dc.w"
            if i.id == 0 or i.mnemonic.startswith("dc"):
                return None
            return i
        return None

    def reloc_in(self, i):
        """Relocated longs inside the instruction's extension words."""
        return [o for o in range(i.address + 2, i.address + i.size - 3, 2) if o in self.reloc]

    def targets(self, i):
        """(code_target, data_targets) for an instruction."""
        code, data = None, []
        rel = self.reloc_in(i)
        for o in rel:
            data.append(self.p.u32(o))
        for m in re.finditer(r"\$([0-9a-f]+)\(pc", i.op_str):
            data.append(int(m.group(1), 16))
        for op in i.operands:
            if op.type == m68k.M68K_OP_BR_DISP:
                code = i.address + 2 + op.br_disp.disp
        mn = i.mnemonic.split(".")[0]
        if mn in ("jmp", "jsr") and code is None:
            if "(pc," in i.op_str or "(a" in i.op_str or "(sp" in i.op_str:
                code = None
            elif data:
                code = data[0]
            if code is not None:
                data = []
        return code, data

    def run(self):
        work = [0] + sorted(self.ctl.roots)
        for addr, count, kind, extra in self.ctl.tables:
            for k in range(count):
                if kind == "w":
                    work.append(extra + self.p.s16(addr + 2 * k))
                else:
                    work.append(self.p.u32(addr + extra * k))
        for w in work:
            if w != 0:
                self.calls.add(w)
        seen = set()
        while work:
            a = work.pop()
            lea = {}            # address register -> last lea target
            while a not in seen:
                i = self.decode(a)
                if i is None:
                    break
                if any(self.owner.get(k, a) != a for k in range(a, a + i.size)):
                    break       # overlaps an instruction already decoded
                seen.add(a)
                self.insn[a] = i
                for k in range(a, a + i.size):
                    self.owner[k] = a
                mn = i.mnemonic.split(".")[0]
                code, data = self.targets(i)
                ml = re.match(r"lea\.l$", i.mnemonic)
                if ml and data:
                    lea[i.op_str.split(",")[-1].strip()] = data[0]
                mv = re.match(r"(a[0-6]), \$([0-9a-f]+)\.[wl]$", i.op_str)
                if mn == "move" and mv and mv.group(1) in lea and is_vector(int(mv.group(2), 16)):
                    work.append(lea[mv.group(1)])
                    self.calls.add(lea[mv.group(1)])
                for d in data:
                    self.datarefs.setdefault(d, set()).add(a)
                    # a code pointer planted in an exception vector
                    if mn == "move" and i.op_str.startswith("#$") and 0 <= d < self.n:
                        dst = i.op_str.split(",")[-1].strip()
                        mdst = re.match(r"\$([0-9a-f]+)\.[wl]$", dst)
                        if mdst and is_vector(int(mdst.group(1), 16)):
                            work.append(d)
                            self.calls.add(d)
                if code is not None:
                    if mn in CALLS:
                        self.calls.add(code)
                    else:
                        self.jumps.add(code)
                    if 0 <= code < self.n:
                        work.append(code)
                elif mn in ("jmp", "jsr"):
                    self.indirect.append((a, f"{i.mnemonic} {i.op_str}"))
                if mn in UNCOND or mn in STOPS:
                    break
                a += i.size

    def code_ranges(self):
        out, start, prev = [], None, None
        for a in sorted(self.insn):
            end = a + self.insn[a].size
            if start is None:
                start, prev = a, end
            elif a == prev:
                prev = end
            else:
                out.append((start, prev))
                start, prev = a, end
        if start is not None:
            out.append((start, prev))
        return out

    def label(self, t):
        if t in self.ctl.labels:
            return self.ctl.labels[t]
        if t in self.calls:
            return f"sub_{t:05X}"
        if t in self.insn or t in self.jumps:
            return f"L_{t:05X}"
        return f"D_{t:05X}"

    def fmt_ops(self, i):
        s = i.op_str
        for o in self.reloc_in(i):
            v = self.p.u32(o)
            s = re.sub(rf"\$0*{v:x}(\.l)?\b", self.label(v), s, count=1)
        s = re.sub(r"\$([0-9a-f]+)\(pc", lambda m: self.label(int(m.group(1), 16)) + "(pc", s)
        code, _ = self.targets(i)
        if code is not None and any(op.type == m68k.M68K_OP_BR_DISP for op in i.operands):
            s = re.sub(r"\$[0-9a-f]+$", self.label(code), s)
        return s

    def listing(self, out):
        labelled = set(self.calls) | set(self.jumps) | set(self.datarefs) | set(self.ctl.labels)
        a = 0
        while a < self.n:
            for c in self.ctl.comments.get(a, []):
                out.write(f"; {c}\n")
            if a in labelled and (a in self.insn or not self.owner.get(a)):
                lab = self.label(a)
                if a in self.calls:
                    out.write("\n")
                out.write(f"{lab}:\n")
            if a in self.insn:
                i = self.insn[a]
                out.write(f"&{a:05X}  {i.bytes.hex():<20} {i.mnemonic:<9} {self.fmt_ops(i)}\n")
                a += i.size
                continue
            # data run up to the next code or label
            end = a + 1
            while end < self.n and end not in self.insn and end not in labelled \
                    and end not in self.ctl.comments and end - a < 16:
                end += 1
            chunk = bytes(self.p.image[a:end])
            text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            rel = [o for o in range(a, end) if o in self.reloc]
            note = "  ; ptr " + " ".join(self.label(self.p.u32(o)) for o in rel) if rel else ""
            out.write(f"&{a:05X}  dc.b {','.join(f'${b:02x}' for b in chunk):<64} |{text}|{note}\n")
            a = end


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg")
    ap.add_argument("--ctl", default=str(Path(__file__).resolve().parent / "st_star.ctl"))
    ap.add_argument("--out")
    ap.add_argument("--map", action="store_true")
    args = ap.parse_args()
    prg = st_prg.load(args.prg)
    d = Disasm(prg, Ctl.read(args.ctl))
    d.run()
    out = open(args.out, "w") if args.out else sys.stdout
    if args.map:
        total = 0
        for s, e in d.code_ranges():
            out.write(f"code &{s:05X}-&{e:05X} {e - s:6d}\n")
            total += e - s
        out.write(f"; {len(d.insn)} instructions, {total} bytes of code reached\n")
        out.write(f"; {len(d.calls)} routines, {len(d.indirect)} unresolved indirect jumps\n")
        for a, t in d.indirect:
            out.write(f"indirect &{a:05X} {t}\n")
        return
    d.listing(out)


if __name__ == "__main__":
    main()
