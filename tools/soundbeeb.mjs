// The disc on jsbeeb's Master for the sound's checks (tools/sfxcheck.mjs,
// tools/speechcheck.mjs): SG loaded and run to engine_run's entry, its
// interrupt on, then the foreground idle at IDLE, with every write to the
// SN76489 timed in CPU cycles; and the writes as each register's values.
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const jsbeeb = (f) => pathToFileURL(path.join(root, "node_modules/jsbeeb/src", f)).href;
const { TestMachine } = await import(jsbeeb("test-machine.js"));
const { SoundChip } = await import(jsbeeb("soundchip.js"));
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc, toGame } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);

export const HZ = 2e6;
export const sym = loadSymbols(path.join(root, "build/starglider.json"));

// The chip, its writes timed, rendering nothing.
class Recorder extends SoundChip {
    constructor() {
        super(() => {});
        this.writes = [];
    }
    advance() {}
    poke(value) {
        this.writes.push([this.scheduler.epoch, value]);
        super.poke(value);
    }
}

// call(routine, a, x) runs LDA #a : LDX #x : JSR routine : JMP IDLE from
// STUB, once the foreground is idle, and gives the cycle it began.
const IDLE = 0x0140, STUB = 0x0143;
export async function machine() {
    const chip = new Recorder();
    const tm = new TestMachine("Master", { soundChip: chip });
    await tm.initialise();
    const q = console.log;
    console.log = () => {};
    await tm.runUntilInput();
    console.log = q;
    loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
    await toGame(tm, sym);
    const cpu = tm.processor;
    const ram = cpu.ramRomOs;
    ram.set([0x4c, IDLE & 0xff, IDLE >> 8], IDLE);
    cpu.pc = IDLE;
    const now = () => cpu.scheduler.epoch;
    const call = async (routine, a = 0, x = 0) => {
        await tm.runUntilAddress(IDLE, 1);
        ram.set([0xa9, a, 0xa2, x, 0x20, routine & 0xff, routine >> 8, 0x4c, IDLE & 0xff, IDLE >> 8], STUB);
        cpu.pc = STUB;
        const t = now();
        await tm.runUntilAddress(IDLE, 1);
        return t;
    };
    const runTo = async (cycle) => {
        const left = cycle - now();
        if (left > 0) await tm.runFor(left);
    };
    return { tm, cpu, ram, chip, now, call, runTo };
}

// The writes as each register's values, in seconds from `from`: tone
// periods (10 bits), the noise's control, attenuations.
export function snEvents(writes, from) {
    const ev = { t0p: [], t0a: [], t1p: [], t1a: [], t2p: [], t2a: [], nctl: [], na: [] };
    const reg = [0, 0, 0, 0];
    let latched = 0;
    for (const [c, v] of writes) {
        const t = (c - from) / HZ;
        if (v & 0x80) latched = v & 0x70;
        const ch = (latched >> 5) & 3;
        if (latched & 0x10) ev[["t0a", "t1a", "t2a", "na"][ch]].push([t, v & 15]);
        else if (ch === 3) ev.nctl.push([t, v & 7]);
        else {
            reg[ch] = v & 0x80 ? (reg[ch] & ~15) | (v & 15) : (reg[ch] & 15) | ((v & 0x3f) << 4);
            ev[["t0p", "t1p", "t2p"][ch]].push([t, reg[ch]]);
        }
    }
    return ev;
}

// Writes a few microseconds apart (a period's two bytes) as one: the last.
export function settle(list, gap = 40e-6) {
    const out = [];
    for (const e of list) {
        if (out.length && e[0] - out[out.length - 1][0] < gap) out[out.length - 1] = e;
        else out.push(e);
    }
    return out;
}
