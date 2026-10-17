#!/usr/bin/env python3
"""A 6502 disassembler with base cycle counts, for the C64 and Apple II code.

    c64_dis.py FILE LOADADDR START [END] [--labels]

FILE is raw bytes loaded at LOADADDR (hex, e.g. 0801 or &0801); START and END
are addresses in that space. Each line shows the address, the bytes, the
instruction and its base cycle count; a '+' marks one more cycle on a page
crossing (indexed reads, taken branches add 1 more and 2 across a page).

Used as a module by the a2_ and c64_ tools: disasm(mem, start, end) yields
(addr, size, mnemonic, operand_text, cycles, target).
"""
import sys
from pathlib import Path

# mode: imp, acc, imm, zp, zpx, zpy, abs, abx, aby, ind, izx, izy, rel
OPS = {}


def _op(code, mn, mode, cyc, plus=False):
    OPS[code] = (mn, mode, cyc, plus)


for code, mn, mode, cyc, plus in [
    (0x69, "ADC", "imm", 2, 0), (0x65, "ADC", "zp", 3, 0), (0x75, "ADC", "zpx", 4, 0),
    (0x6D, "ADC", "abs", 4, 0), (0x7D, "ADC", "abx", 4, 1), (0x79, "ADC", "aby", 4, 1),
    (0x61, "ADC", "izx", 6, 0), (0x71, "ADC", "izy", 5, 1),
    (0x29, "AND", "imm", 2, 0), (0x25, "AND", "zp", 3, 0), (0x35, "AND", "zpx", 4, 0),
    (0x2D, "AND", "abs", 4, 0), (0x3D, "AND", "abx", 4, 1), (0x39, "AND", "aby", 4, 1),
    (0x21, "AND", "izx", 6, 0), (0x31, "AND", "izy", 5, 1),
    (0x0A, "ASL", "acc", 2, 0), (0x06, "ASL", "zp", 5, 0), (0x16, "ASL", "zpx", 6, 0),
    (0x0E, "ASL", "abs", 6, 0), (0x1E, "ASL", "abx", 7, 0),
    (0x90, "BCC", "rel", 2, 1), (0xB0, "BCS", "rel", 2, 1), (0xF0, "BEQ", "rel", 2, 1),
    (0x30, "BMI", "rel", 2, 1), (0xD0, "BNE", "rel", 2, 1), (0x10, "BPL", "rel", 2, 1),
    (0x50, "BVC", "rel", 2, 1), (0x70, "BVS", "rel", 2, 1),
    (0x24, "BIT", "zp", 3, 0), (0x2C, "BIT", "abs", 4, 0),
    (0x00, "BRK", "imp", 7, 0),
    (0x18, "CLC", "imp", 2, 0), (0xD8, "CLD", "imp", 2, 0), (0x58, "CLI", "imp", 2, 0),
    (0xB8, "CLV", "imp", 2, 0),
    (0xC9, "CMP", "imm", 2, 0), (0xC5, "CMP", "zp", 3, 0), (0xD5, "CMP", "zpx", 4, 0),
    (0xCD, "CMP", "abs", 4, 0), (0xDD, "CMP", "abx", 4, 1), (0xD9, "CMP", "aby", 4, 1),
    (0xC1, "CMP", "izx", 6, 0), (0xD1, "CMP", "izy", 5, 1),
    (0xE0, "CPX", "imm", 2, 0), (0xE4, "CPX", "zp", 3, 0), (0xEC, "CPX", "abs", 4, 0),
    (0xC0, "CPY", "imm", 2, 0), (0xC4, "CPY", "zp", 3, 0), (0xCC, "CPY", "abs", 4, 0),
    (0xC6, "DEC", "zp", 5, 0), (0xD6, "DEC", "zpx", 6, 0), (0xCE, "DEC", "abs", 6, 0),
    (0xDE, "DEC", "abx", 7, 0),
    (0xCA, "DEX", "imp", 2, 0), (0x88, "DEY", "imp", 2, 0),
    (0x49, "EOR", "imm", 2, 0), (0x45, "EOR", "zp", 3, 0), (0x55, "EOR", "zpx", 4, 0),
    (0x4D, "EOR", "abs", 4, 0), (0x5D, "EOR", "abx", 4, 1), (0x59, "EOR", "aby", 4, 1),
    (0x41, "EOR", "izx", 6, 0), (0x51, "EOR", "izy", 5, 1),
    (0xE6, "INC", "zp", 5, 0), (0xF6, "INC", "zpx", 6, 0), (0xEE, "INC", "abs", 6, 0),
    (0xFE, "INC", "abx", 7, 0),
    (0xE8, "INX", "imp", 2, 0), (0xC8, "INY", "imp", 2, 0),
    (0x4C, "JMP", "abs", 3, 0), (0x6C, "JMP", "ind", 5, 0), (0x20, "JSR", "abs", 6, 0),
    (0xA9, "LDA", "imm", 2, 0), (0xA5, "LDA", "zp", 3, 0), (0xB5, "LDA", "zpx", 4, 0),
    (0xAD, "LDA", "abs", 4, 0), (0xBD, "LDA", "abx", 4, 1), (0xB9, "LDA", "aby", 4, 1),
    (0xA1, "LDA", "izx", 6, 0), (0xB1, "LDA", "izy", 5, 1),
    (0xA2, "LDX", "imm", 2, 0), (0xA6, "LDX", "zp", 3, 0), (0xB6, "LDX", "zpy", 4, 0),
    (0xAE, "LDX", "abs", 4, 0), (0xBE, "LDX", "aby", 4, 1),
    (0xA0, "LDY", "imm", 2, 0), (0xA4, "LDY", "zp", 3, 0), (0xB4, "LDY", "zpx", 4, 0),
    (0xAC, "LDY", "abs", 4, 0), (0xBC, "LDY", "abx", 4, 1),
    (0x4A, "LSR", "acc", 2, 0), (0x46, "LSR", "zp", 5, 0), (0x56, "LSR", "zpx", 6, 0),
    (0x4E, "LSR", "abs", 6, 0), (0x5E, "LSR", "abx", 7, 0),
    (0xEA, "NOP", "imp", 2, 0),
    (0x09, "ORA", "imm", 2, 0), (0x05, "ORA", "zp", 3, 0), (0x15, "ORA", "zpx", 4, 0),
    (0x0D, "ORA", "abs", 4, 0), (0x1D, "ORA", "abx", 4, 1), (0x19, "ORA", "aby", 4, 1),
    (0x01, "ORA", "izx", 6, 0), (0x11, "ORA", "izy", 5, 1),
    (0x48, "PHA", "imp", 3, 0), (0x08, "PHP", "imp", 3, 0), (0x68, "PLA", "imp", 4, 0),
    (0x28, "PLP", "imp", 4, 0),
    (0x2A, "ROL", "acc", 2, 0), (0x26, "ROL", "zp", 5, 0), (0x36, "ROL", "zpx", 6, 0),
    (0x2E, "ROL", "abs", 6, 0), (0x3E, "ROL", "abx", 7, 0),
    (0x6A, "ROR", "acc", 2, 0), (0x66, "ROR", "zp", 5, 0), (0x76, "ROR", "zpx", 6, 0),
    (0x6E, "ROR", "abs", 6, 0), (0x7E, "ROR", "abx", 7, 0),
    (0x40, "RTI", "imp", 6, 0), (0x60, "RTS", "imp", 6, 0),
    (0xE9, "SBC", "imm", 2, 0), (0xE5, "SBC", "zp", 3, 0), (0xF5, "SBC", "zpx", 4, 0),
    (0xED, "SBC", "abs", 4, 0), (0xFD, "SBC", "abx", 4, 1), (0xF9, "SBC", "aby", 4, 1),
    (0xE1, "SBC", "izx", 6, 0), (0xF1, "SBC", "izy", 5, 1),
    (0x38, "SEC", "imp", 2, 0), (0xF8, "SED", "imp", 2, 0), (0x78, "SEI", "imp", 2, 0),
    (0x85, "STA", "zp", 3, 0), (0x95, "STA", "zpx", 4, 0), (0x8D, "STA", "abs", 4, 0),
    (0x9D, "STA", "abx", 5, 0), (0x99, "STA", "aby", 5, 0), (0x81, "STA", "izx", 6, 0),
    (0x91, "STA", "izy", 6, 0),
    (0x86, "STX", "zp", 3, 0), (0x96, "STX", "zpy", 4, 0), (0x8E, "STX", "abs", 4, 0),
    (0x84, "STY", "zp", 3, 0), (0x94, "STY", "zpx", 4, 0), (0x8C, "STY", "abs", 4, 0),
    (0xAA, "TAX", "imp", 2, 0), (0xA8, "TAY", "imp", 2, 0), (0xBA, "TSX", "imp", 2, 0),
    (0x8A, "TXA", "imp", 2, 0), (0x9A, "TXS", "imp", 2, 0), (0x98, "TYA", "imp", 2, 0),
]:
    _op(code, mn, mode, cyc, bool(plus))

SIZE = {"imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2, "abs": 3, "abx": 3,
        "aby": 3, "ind": 3, "izx": 2, "izy": 2, "rel": 2}


def fmt(mode, val):
    if val is None:
        return "A" if mode == "acc" else ""
    return {
        "imp": "", "acc": "A", "imm": f"#&{val:02X}", "zp": f"&{val:02X}",
        "zpx": f"&{val:02X},X", "zpy": f"&{val:02X},Y", "abs": f"&{val:04X}",
        "abx": f"&{val:04X},X", "aby": f"&{val:04X},Y", "ind": f"(&{val:04X})",
        "izx": f"(&{val:02X},X)", "izy": f"(&{val:02X}),Y", "rel": f"&{val:04X}",
    }[mode]


def decode(mem, addr):
    """mem: callable or bytes-like indexed by address. Returns a tuple or None."""
    get = mem if callable(mem) else (lambda a: mem[a])
    op = get(addr)
    if op not in OPS:
        return None
    mn, mode, cyc, plus = OPS[op]
    n = SIZE[mode]
    if n == 1:
        val = None
    elif n == 2:
        val = get(addr + 1)
        if mode == "rel":
            val = (addr + 2 + (val - 256 if val & 0x80 else val)) & 0xFFFF
    else:
        val = get(addr + 1) | get(addr + 2) << 8
    target = val if mode in ("rel", "abs") and mn in ("JMP", "JSR", "BCC", "BCS", "BEQ",
                                                     "BMI", "BNE", "BPL", "BVC", "BVS") else None
    return n, mn, fmt(mode, val), cyc, plus, target, mode, val


def disasm(mem, start, end):
    a = start
    while a < end:
        d = decode(mem, a)
        if d is None:
            yield a, 1, "???", "", 0, None
            a += 1
            continue
        n, mn, txt, cyc, plus, target, _mode, _val = d
        yield a, n, mn, txt, f"{cyc}{'+' if plus else ''}", target
        a += n


class Mem:
    def __init__(self, data, base):
        self.data, self.base = data, base

    def __call__(self, a):
        i = a - self.base
        return self.data[i] if 0 <= i < len(self.data) else 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    h = lambda s: int(s.lstrip("&$"), 16)
    data = Path(args[0]).read_bytes()
    base = h(args[1])
    start = h(args[2])
    end = h(args[3]) if len(args) > 3 else base + len(data)
    mem = Mem(data, base)
    for a, n, mn, txt, cyc, target in disasm(mem, start, end):
        raw = " ".join(f"{mem(a + i):02X}" for i in range(n))
        print(f"&{a:04X}  {raw:<9} {mn} {txt:<12} ; {cyc}")


if __name__ == "__main__":
    main()
