// Check the port's game logic against the ST's, routine by routine, on
// jsbeeb's Master (decision 1: the logic exact).
//
//   node tools/logicrun.mjs STEPS.json ROUTINE [--build build/spike] [--show N] [--cycles]
//
// STEPS.json is tools/st_steps.py's capture. For every frame with both
// the routine's entry and exit points, the ST's state at the entry is put
// into the port's by the map (tools/stmap.py: the variables declared with
// {ST ...}, and the object table), the port's routine is run (the spike's
// spike_logic, with its bank and ANDY paged), and everything the map holds
// is compared with the ST's state at the exit. It prints, for each
// variable or field that ever differs, the frames it differs in and the
// first few, and exits non-zero if any did. --cycles adds what the routine
// took on the frames (jsbeeb's count, the call's own few included).
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./beeb.mjs";

// The routines: their entry and exit points in the capture, the port's
// routine, and its bank; and whether the ST's d0 at the exit is compared
// (where a later random8 adds it, or one within the routine adds what
// the routine's earlier work left, as the mines' does).
// An exit point "next:P" is P in the next frame; "unless" skips the frames
// with that point (the post-frame tests, when they go to the level change).
// "inputs" names a point to take the inputs ("in" variables) from, where
// the frame has it: where the routine reads them, nearer than its entry.
// With x, the routine is called with X the slot of the record the ST's a0
// points to at the entry point (a handler's object). A frame whose order
// (tools/st_steps.py) has a capture script's write inside a routine's span
// is left out for that routine. A variable marked `in` is given to the
// routine but never compared.
const ROUTINES = {
    world: { from: "top", to: "lists", call: "world_lists", bank: "BANK_WORLD" },
    world_after: { from: "lists", to: "render", call: "world_after", bank: "BANK_LOGIC" },
    // (both halves: the missile view has no lists point; the laser reads
    // the keys after the lists)
    world_whole: { from: "top", to: "render", call: "world_whole", bank: "BANK_WORLD", inputs: "lists" },
    keys: { from: "render", to: "keys", call: "read_keys", bank: "BANK_LOGIC" },
    flight: { from: "keys", to: "flight", call: "player_flight", bank: "BANK_WORLD", d0: true },
    handlers: { from: "flight", to: "handlers", call: "object_handlers", bank: "BANK_WORLD", d0: true },
    animate: { from: "handlers", to: "animate", call: "animate_shapes", bank: "BANK_WORLD" },
    collide: { from: "animate", to: "collide", call: "collisions", bank: "BANK_LOGIC" },
    message: { from: "collide", to: "message", call: "level_message", bank: "BANK_LOGIC" },
    frame_end: { from: "message", to: "end", call: "frame_end_logic", bank: "BANK_LOGIC" },
    post: { from: "end", to: "next:top", call: "post_frame", bank: "BANK_LOGIC", unless: "level" },
    mine: { from: "mine", to: "mined", call: "mine_proximity", bank: "BANK_LOGIC", x: true },
    level: { from: "level", to: "next:top", call: "level_start", bank: "BANK_LOGIC", d0: true },
    newgame: { from: "newgame", to: "level", call: "new_game", bank: "BANK_LOGIC" },
    // a whole step as the disc takes it (src/step.6502), the keys as
    // read_keys found them
    step: { from: "top", to: "next:top", call: "spike_step", bank: "BANK_WORLD", inputs: "render" },
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
const cycles = args.includes("--cycles") ? (args.splice(args.indexOf("--cycles"), 1), []) : null;
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
load("LOGIC", bank(need("BANK_LOGIC")));
// (ground_dots rotates by the drawing's ground rotation, in the loading
// area's bank with the view's code)
load("WINDOW", bank(need("BANK_PIC")) + need("WIN_PIC") - 0x8000);

const STUB = 0x0140;
const STUB_DONE = STUB + 6;
async function run(entry, x = 0) {
    ram.set([0x78, 0xa2, x, 0x20, entry & 0xff, entry >> 8, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);
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

// The ST's long at an address, from whichever region holds it.
function stLong(r, addr) {
    for (const [name, start, n] of steps.regions)
        if (addr >= start && addr + 4 <= start + n) return r[name].readUInt32BE(addr - start);
    throw new Error(`&${addr.toString(16)} isn't in the capture's regions`);
}

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
    } else if (v.kind === "slots") {
        const long = (r, i) => st(r).readUInt32BE(v.offset + 4 * i);
        items.push({
            name: v.name,
            put: (r) => {
                for (let i = 0; i < v.count; i++) ram[at + i] = slotOf(long(r, i));
            },
            get: () => Array.from({ length: v.count }, (_, i) => ptrOf(ram[at + i])),
            want: (r) => Array.from({ length: v.count }, (_, i) => long(r, i)),
        });
    } else if (v.kind === "index") {
        // A pointer outside its array is one the ST hasn't set yet (0, until
        // init_objects first sets the free stack's): the port, which keeps
        // the entry's number, holds nothing for it, so it's neither put nor
        // compared.
        const long = (r) => st(r).readUInt32BE(v.offset);
        const entry = (r) => (long(r) - v.base) / v.stride;
        const set = (r) => Number.isInteger(entry(r)) && entry(r) >= 0 && entry(r) <= 255;
        items.push({
            name: v.name,
            put: (r) => {
                if (set(r)) ram[at] = entry(r);
            },
            get: () => [v.base + v.stride * ram[at]],
            want: (r) => (set(r) ? [long(r)] : [v.base + v.stride * ram[at]]),
        });
    } else if (v.kind === "list") {
        // the entries from the ST's pointer up, the first walked first,
        // which the port keeps in the order pushed (walked from its end),
        // with its count before them
        const count = (r) => r[v.count_region].readUInt16BE(v.count_offset);
        const entries = (r) => {
            const p = st(r).readUInt32BE(v.offset);
            return Array.from({ length: count(r) }, (_, k) => stLong(r, p + 4 * k));
        };
        items.push({
            name: v.name,
            put: (r) => {
                const e = entries(r);
                ram[v.count_at] = e.length;
                e.forEach((ptr, k) => (ram[at + e.length - 1 - k] = slotOf(ptr)));
            },
            get: () => {
                const n = ram[v.count_at];
                return [n, ...Array.from({ length: n }, (_, k) => ptrOf(ram[at + n - 1 - k]))];
            },
            want: (r) => [count(r), ...entries(r)],
        });
    } else if (v.kind === "slotsdown") {
        // a list pushed downward from the address: the first entry is the
        // long just below it
        const long = (r, i) => st(r).readUInt32BE(v.offset - 4 * (i + 1));
        items.push({
            name: v.name,
            put: (r) => {
                for (let i = 0; i < v.count; i++) ram[at + i] = slotOf(long(r, i));
            },
            get: () => Array.from({ length: v.count }, (_, i) => ptrOf(ram[at + i])),
            want: (r) => Array.from({ length: v.count }, (_, i) => long(r, i)),
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
    if (v.input) items[items.length - 1].input = true;
}
// (an input, which the ST's interrupts write when they will, is put, not
// compared)
for (const v of map.variables) if (v.input) items.find((it) => it.name === v.name).input = true;
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
// The camera-space positions of the objects the list phase rotated
// approximately (decision 11, ob_exact 0) are the ST's only to within the
// approximation's bound in x and z (ROT_BOUND, tools/mkrotate.py's), and
// only for an object the ST neither drew nor had within NEAR_BOX of the
// player in x and z (decision 31; tools/scenecheck.py's rule): a slot that
// keeps to that is taken as matching. Their y' isn't made at all (decision
// 21). Drawn is the ST's draw list at the exit, not the record's flag: the
// silo's two records keep what TOS left in theirs, which nothing clears.
// One the list phase found far off (decision 47) has a sentinel in both,
// taken as matching for an object the ST has where nothing reads them:
// neither drawn nor near, nor in the scanner's square (-&2000 to &2000).
const ROT_BOUND = need("ROT_BOUND");
const NEAR_BOX = need("NEAR_BOX");
const FAR_X = need("FAR_X");
const sentinel = (s) => ram[need("ob_cx_hi") + s] === FAR_X >> 8 && ram[need("ob_cz_hi") + s] === FAR_X >> 8;
const exactAt = need("ob_exact");
const drawList = items.find((it) => it.name === "st_draw_list");
const camera = ["ob_cx", "ob_cy", "ob_cz"].map((n) => items.find((it) => it.name === n));
const s16 = (v) => (v & 0x8000 ? v - 0x10000 : v);
for (const it of camera)
    it.approx = (got, want, exit) => {
        for (let s = 0; s < got.length; s++) {
            if (got[s] === want[s] || ram[exactAt + s]) continue;
            if (it.name === "ob_cy") {
                got[s] = want[s];
                continue;
            }
            const st = [camera[0], camera[2]].map((c) => s16(c.want(exit)[s]));
            const drawn = drawList.want(exit).slice(1).some((ptr) => slotOf(ptr) === s);
            if (sentinel(s)) {
                const near = st.every((c) => Math.abs(c) <= NEAR_BOX);
                const scanned = st.every((c) => Math.abs(c) < 0x2000);
                if (!drawn && !near && !scanned) got[s] = want[s];
                continue;
            }
            const off = Math.abs(s16((got[s] - want[s]) & 0xffff));
            if (off <= ROT_BOUND && !drawn && !st.every((c) => Math.abs(c) <= NEAR_BOX)) got[s] = want[s];
        }
    };

ram[need("logic_bank")] = need(routine.bank) | need("ROMSEL_ANDY");
ram[need("logic_call")] = need(routine.call) & 0xff;
ram[need("logic_call") + 1] = need(routine.call) >> 8;
const diffs = new Map();
let frames = 0;
let poked = 0;
const differ = (name, n, got, want) => {
    if (!diffs.has(name)) diffs.set(name, []);
    diffs.get(name).push({ frame: n, got, want });
};
for (let n = 0; n < steps.frames.length; n++) {
    const fr = steps.frames[n];
    const next = routine.to.startsWith("next:");
    const exitFrame = next ? steps.frames[n + 1] : fr;
    const exitPoint = next ? routine.to.slice(5) : routine.to;
    if (!exitFrame || (routine.unless && fr.points[routine.unless])) continue;
    const entry = regionsAt(fr, routine.from);
    const exit = regionsAt(exitFrame, exitPoint);
    if (!entry || !exit) continue;
    // a write of the capture script's anywhere in the span is in the ST's
    // result, but no routine's
    const order = fr.order || [];
    const start = order.lastIndexOf(routine.from);
    const exitOrder = exitFrame.order || [];
    const inSpan = next
        ? order.slice(start + 1).includes("poke") || exitOrder.slice(0, exitOrder.indexOf(exitPoint)).includes("poke")
        : order.slice(start + 1, order.lastIndexOf(exitPoint)).includes("poke");
    if (inSpan) {
        poked++;
        continue;
    }
    frames++;
    const given = (routine.inputs && regionsAt(fr, routine.inputs)) || entry;
    for (const it of items) it.put(it.input ? given : entry);
    const rngD0 = need("rng_d0");
    const d0 = fr.d0 ?? {};                     // (older captures have no d0)
    ram[rngD0] = (d0[routine.from] ?? 0) & 0xff;
    ram[rngD0 + 1] = (d0[routine.from] ?? 0) >> 8;
    const t0 = tm.elapsedCycles;
    await run(need("spike_logic"), routine.x ? slotOf(fr.a0[routine.from]) : 0);
    if (cycles) cycles.push(tm.elapsedCycles - t0);
    for (const it of items) {
        if (it.input) continue;
        const got = it.get();
        const want = it.want(exit);
        if (it.approx) it.approx(got, want, exit);
        if (got.some((x, i) => x !== want[i])) {
            const at = got.findIndex((x, i) => x !== want[i]);
            differ(it.name, n, got.length > 2 ? `[${at}] ${got[at]}` : got.join(" "), want.length > 2 ? `[${at}] ${want[at]}` : want.join(" "));
        }
    }
    const exitD0 = exitFrame.d0 ?? {};
    if (routine.d0 && exitPoint in exitD0) {
        const got = ram[rngD0] | (ram[rngD0 + 1] << 8);
        if (got !== exitD0[exitPoint]) differ("d0 (rng_d0)", n, got, exitD0[exitPoint]);
    }
}
console.log(
    `logicrun ${routineName}: ${frames} frames` +
        (poked ? ` (${poked} more with the script's writes in)` : "") +
        `, ${items.length} variables and fields, ${diffs.size} differ`,
);
if (cycles && cycles.length)
    console.log(`  cycles: mean ${Math.round(cycles.reduce((a, b) => a + b, 0) / cycles.length)}, least ${Math.min(...cycles)}, most ${Math.max(...cycles)}`);
for (const [name, list] of diffs) {
    console.log(`  ${name}: ${list.length} frames, e.g. ` + list.slice(0, show).map((d) => `frame ${d.frame} port ${d.got} ST ${d.want}`).join("; "));
}
process.exit(diffs.size ? 1 : 0);
