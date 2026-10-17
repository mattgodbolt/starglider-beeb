"""SkoolKit's Z80 simulator with all 64K writable, for running CPC code headless.

SkoolKit's Simulator protects &0000-&3FFF as the Spectrum's ROM. The CPC game
keeps code, self-modified operands and data there, so this loads the
simulator's source with that check removed. Nothing else changes.

    from cpc_z80 import CPCSimulator, run_call
"""
import inspect
import types

import skoolkit.simulator as _sim
from skoolkit.simutils import PC, SP  # noqa: F401  (re-exported for callers)

_src = inspect.getsource(_sim).replace("> 0x3FFF", ">= 0")
_mod = types.ModuleType("cpc_simulator")
exec(compile(_src, "cpc_simulator", "exec"), _mod.__dict__)
CPCSimulator = _mod.Simulator

SENTINEL = 0xFFFE


def run_call(sim, address, stop=SENTINEL, sp=0xFE00, max_steps=5_000_000):
    """CALL address with a sentinel return address and run until it returns.

    Returns the number of instructions executed. Raises if max_steps is reached.
    """
    mem, regs = sim.memory, sim.registers
    sp = (sp - 2) & 0xFFFF
    mem[sp] = stop & 0xFF
    mem[sp + 1] = stop >> 8
    regs[SP] = sp
    regs[PC] = address
    steps = 0
    while regs[PC] != stop:
        sim.run()
        steps += 1
        if steps >= max_steps:
            raise RuntimeError(f"no return from &{address:04X} after {steps} steps (PC=&{regs[PC]:04X})")
    return steps
