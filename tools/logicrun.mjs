// Check the port's game logic against the ST's, routine by routine, on
// jsbeeb's Master (decision 1: the logic exact).
//
//   node tools/logicrun.mjs STEPS.json ROUTINE [--build build/spike] [--show N]
//
// STEPS.json is tools/st_steps.py's capture. For every frame with both
// the routine's entry and exit points, the ST's state at the entry is put
// into the port's by the map (tools/stmap.py: the variables declared with
// {ST ...}, and the object table), the port's routine is run (the spike's
// spike_logic, with its bank and ANDY paged), and everything the map holds
// is compared with the ST's state at the exit. It prints, for each
// variable or field that ever differs, the frames it differs in and the
// first few, and exits non-zero if any did.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./beeb.mjs";

// The routines: their entry and exit points in the capture, the port's
// routine, and its bank; and whether the ST's d0 at the exit is compared
// (where a later random8 adds it).
const ROUTINES = {
    animate: { from: "handlers", to: "animate", call: "animate_shapes", bank: "BANK_WORLD" },
    flight: { from: "keys", to: "flight", call: "player_flight", bank: "BANK_WORLD", d0: true },
};

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const build = opt("--build", "build/spike");
const show = Number(opt("--show", 3));
const [stepsPath, routineName] = args;
const routine = ROUTINES[routineName];
if (!stepsPath || !routine) {
    console.error(`usage: node tools/logicrun.mjs STEPS.json ROUTINE   (${Object.keys(ROUTINES).join(", ")})`);
    process.exit(2);
}

const sym = loadSymbols(path.join(build, "symbols.json"));
const need = (name) => {
    if (!(name in sym)) throw new Error(`no symbol ${name}`);
    return sym[name];
};
const map = JSON.parse(execFileSync("python3", ["-I", "tools/stmap.py", path.join(build, "symbols.json")], { encoding: "utf8" }));
const steps = JSON.parse(fs.readFileSync(stepsPath, "utf8"));

const jsbeeb = path.resolve("node_modules/jsbeeb/src/test-machine.js");
const { TestMachine } = await import(pathToFileURL(jsbeeb).href);
const tm = new TestMachine("Master");
await tm.initialise();
const quiet = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = quiet;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;
const where = (a) => (a >= 0xc000 && a < 0xe000 ? 0x9000 + (a - 0xc000) : a);   // HAZEL; ANDY is at &8000 as it is
const load = (file, at) => ram.set(fs.readFileSync(path.join(build, file)), at);
load("SPIKE", need("spike_init"));
load("TABLES", where(need("TABLES")));
load("CODE2", where(need("CODE2")));
load("SHAPES", bank(need("BANK_SHAPES")));
load("WORLD", bank(need("BANK_WORLD")));

const STUB = 0x0140;
const STUB_DONE = STUB + 4;
async function run(entry) {
    ram.set([0x78, 0x20, entry & 0xff, entry >> 8, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);
    cpu.pc = STUB;
    cpu.s = 0xff;
    await tm.runUntilAddress(STUB_DONE, 5);
    if (cpu.pc !== STUB_DONE) throw new Error(`&${entry.toString(16)} didn't return: pc &${cpu.pc.toString(16)}`);
}
await run(need("spike_init"));

// The ST's state at a point, as byte arrays by region.
const regionsAt = (frame, point) => {
    const p = frame.points[point];
    if (!p) return null;
    const out = {};
    for (const [name, hex] of Object.entries(p)) out[name] = Buffer.from(hex, "hex");
    return out;
};

// Each variable and field: put (ST into the port) and get (the port as
// the ST's bytes, to compare with the ST's own).
function slotOf(ptr) {
    if (ptr === 0) return 0xff;
    if (ptr === 0x1218) return 140;
    if (ptr === 0x1258) return 141;
    const s = (ptr - (0x5bf00 + map.records.offset)) / map.records.size;
    if (!Number.isInteger(s) || s < 0 || s >= 140) throw new Error(`not a record: &${ptr.toString(16)}`);
    return s;
}
function ptrOf(slot) {
    if (slot === 0xff) return 0;
    if (slot === 140) return 0x1218;
    if (slot === 141) return 0x1258;
    return 0x5bf00 + map.records.offset + map.records.size * slot;
}
const items = [];
for (const v of map.variables) {
    const at = v.at;
    const st = (r) => r[v.region];
    if (v.kind === "byte") items.push({ name: v.name, put: (r) => (ram[at] = st(r)[v.offset]), get: () => [ram[at]], want: (r) => [st(r)[v.offset]] });
    else if (v.kind === "word")
        items.push({
            name: v.name,
            put: (r) => {
                ram[at] = st(r)[v.offset + 1];
                ram[at + 1] = st(r)[v.offset];
            },
            get: () => [ram[at + 1], ram[at]],
            want: (r) => [st(r)[v.offset], st(r)[v.offset + 1]],
        });
    else if (v.kind === "word8")
        items.push({ name: v.name, put: (r) => (ram[at] = st(r)[v.offset + 1]), get: () => [0, ram[at]], want: (r) => [st(r)[v.offset], st(r)[v.offset + 1]] });
    else if (v.kind === "long")
        items.push({
            name: v.name,
            put: (r) => {
                for (let i = 0; i < 4; i++) ram[at + i] = st(r)[v.offset + 3 - i];
            },
            get: () => [3, 2, 1, 0].map((i) => ram[at + i]),
            want: (r) => [...st(r).subarray(v.offset, v.offset + 4)],
        });
    else if (v.kind === "raw")
        items.push({
            name: v.name,
            put: (r) => ram.set(st(r).subarray(v.offset, v.offset + v.count), at),
            get: () => [...ram.subarray(at, at + v.count)],
            want: (r) => [...st(r).subarray(v.offset, v.offset + v.count)],
        });
    else if (v.kind === "wlo" || v.kind === "whi" || v.kind === "barr") {
        const k = v.kind === "wlo" ? 1 : 0;
        const idx = (i) => v.offset + i * v.stride + k;
        items.push({
            name: v.name,
            put: (r) => {
                for (let i = 0; i < v.count; i++) ram[at + i] = st(r)[idx(i)];
            },
            get: () => [...ram.subarray(at, at + v.count)],
            want: (r) => Array.from({ length: v.count }, (_, i) => st(r)[idx(i)]),
        });
    } else if (v.kind === "slot") {
        const long = (r) => st(r).readUInt32BE(v.offset);
        items.push({
            name: v.name,
            put: (r) => (ram[at] = slotOf(long(r))),
            get: () => [ptrOf(ram[at])],
            want: (r) => [long(r)],
        });
    } else throw new Error(`${v.name}: kind ${v.kind}`);
}
// The object table, a field at a time across the slots.
const rec = (r, s) =>
    s < 140
        ? r[map.records.region].subarray(map.records.offset + 64 * s, map.records.offset + 64 * s + 64)
        : r[map.records.silo.region].subarray(64 * (s - 140), 64 * (s - 140) + 64);
for (const f of map.objects) {
    const n = f.slots;
    const [lo, hi] = f.at;
    const each = (fn) => Array.from({ length: n }, (_, s) => fn(s));
    if (f.kind === "byte")
        items.push({ name: f.name, put: (r) => each((s) => (ram[lo + s] = rec(r, s)[f.field])), get: () => each((s) => ram[lo + s]), want: (r) => each((s) => rec(r, s)[f.field]) });
    else if (f.kind === "word8")
        // (the silo's two keep what TOS left in the fields the game never
        // writes for them, a high byte among it: their low byte is compared)
        items.push({
            name: f.name,
            put: (r) => each((s) => (ram[lo + s] = rec(r, s)[f.field + 1])),
            get: () => each((s) => ram[lo + s]),
            want: (r) => each((s) => (s >= 140 ? 0 : rec(r, s)[f.field] << 8) | rec(r, s)[f.field + 1]),
        });
    else if (f.kind === "word")
        items.push({
            name: f.name,
            put: (r) =>
                each((s) => {
                    ram[lo + s] = rec(r, s)[f.field + 1];
                    ram[hi + s] = rec(r, s)[f.field];
                }),
            get: () => each((s) => ram[lo + s] | (ram[hi + s] << 8)),
            want: (r) => each((s) => (rec(r, s)[f.field] << 8) | rec(r, s)[f.field + 1]),
        });
    else if (f.kind === "zero")     // not kept: always 0 (but in the silo's two, which keep what TOS left)
        items.push({ name: f.name, put: () => {}, get: () => each(() => 0), want: (r) => each((s) => (s >= 140 ? 0 : (rec(r, s)[f.field] << 8) | rec(r, s)[f.field + 1])) });
}

ram[need("logic_bank")] = need(routine.bank) | need("ROMSEL_ANDY");
ram[need("logic_call")] = need(routine.call) & 0xff;
ram[need("logic_call") + 1] = need(routine.call) >> 8;
const diffs = new Map();
let frames = 0;
const differ = (name, n, got, want) => {
    if (!diffs.has(name)) diffs.set(name, []);
    diffs.get(name).push({ frame: n, got, want });
};
for (let n = 0; n < steps.frames.length; n++) {
    const fr = steps.frames[n];
    const entry = regionsAt(fr, routine.from);
    const exit = regionsAt(fr, routine.to);
    if (!entry || !exit) continue;
    frames++;
    for (const it of items) it.put(entry);
    const rngD0 = need("rng_d0");
    const d0 = fr.d0 ?? {};                     // (older captures have no d0)
    ram[rngD0] = (d0[routine.from] ?? 0) & 0xff;
    ram[rngD0 + 1] = (d0[routine.from] ?? 0) >> 8;
    await run(need("spike_logic"));
    for (const it of items) {
        const got = it.get();
        const want = it.want(exit);
        if (got.some((x, i) => x !== want[i])) {
            const at = got.findIndex((x, i) => x !== want[i]);
            differ(it.name, n, got.length > 2 ? `[${at}] ${got[at]}` : got.join(" "), want.length > 2 ? `[${at}] ${want[at]}` : want.join(" "));
        }
    }
    if (routine.d0 && routine.to in d0) {
        const got = ram[rngD0] | (ram[rngD0 + 1] << 8);
        if (got !== fr.d0[routine.to]) differ("d0 (rng_d0)", n, got, fr.d0[routine.to]);
    }
}
console.log(`logicrun ${routineName}: ${frames} frames, ${items.length} variables and fields, ${diffs.size} differ`);
for (const [name, list] of diffs) {
    console.log(`  ${name}: ${list.length} frames, e.g. ` + list.slice(0, show).map((d) => `frame ${d.frame} port ${d.got} ST ${d.want}`).join("; "));
}
process.exit(diffs.size ? 1 : 0);
