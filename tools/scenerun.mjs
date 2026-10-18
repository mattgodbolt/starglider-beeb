// Run scenes through the port's renderer on jsbeeb's Master, and record
// what it makes of them and how long each part takes.
//
//   node tools/scenerun.mjs SCENES.json OUT.json [--build build/spike] [--frames A-B] [--profile N]
//
// SCENES.json is tools/mkscene.py's: each frame's objects (the ST's
// records), inputs and animation frames. The build directory holds the
// spike's binaries (SPIKE, SHAPES, WORLD) and its symbols.json. Each frame
// is written into memory, the records into the port's object table by
// build/gen/objects.json (decision 13's layout, tools/mkobjects.py),
// spike_frame is called from a stub with interrupts off, and the
// cycles are jsbeeb's own count between the phases' labels (render,
// render_lists, render_objects, render_done). tools/scenecheck.py
// compares OUT.json with the ST's renderer.
//
// --profile N samples the program counter every N cycles instead of
// timing the phases, and prints each routine's share: the routine is the
// nearest label before the sample that isn't inside a scope, and each
// generated file's labels (line, rotate, xform) count as one.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./beeb.mjs";

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const build = opt("--build", "build/spike");
const frameRange = opt("--frames", null);
const profileEvery = Number(opt("--profile", 0));
const [scenesPath, outPath] = args;
if (!scenesPath || !outPath) {
    console.error("usage: node tools/scenerun.mjs SCENES.json OUT.json [--build DIR] [--frames A-B]");
    process.exit(2);
}

const jsbeeb = path.resolve("node_modules/jsbeeb/src/test-machine.js");
const { TestMachine } = await import(pathToFileURL(jsbeeb).href);
const sym = loadSymbols(path.join(build, "symbols.json"));
const need = (name) => {
    if (!(name in sym)) throw new Error(`no symbol ${name}`);
    return sym[name];
};

const tm = new TestMachine("Master");
await tm.initialise();
const quiet = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = quiet;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;

// HAZEL (&C000-&DFFF, paged by the spike) is at &9000 in jsbeeb's array.
const where = (a) => (a >= 0xc000 && a < 0xe000 ? 0x9000 + (a - 0xc000) : a);
const load = (file, at) => {
    const data = fs.readFileSync(path.join(build, file));
    ram.set(data, at);
};
load("SPIKE", need("spike_init"));
load("TABLES", where(need("TABLES")));
load("CODE2", where(need("CODE2")));
load("SHAPES", bank(need("BANK_SHAPES")));
load("WORLD", bank(need("BANK_WORLD")));

// The stub: SEI, JSR entry, JMP to itself.
const STUB = 0x0140;
const STUB_DONE = STUB + 4;
ram.set([0x78, 0x20, 0, 0, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);

// The routines by address, for the profile.
function routines() {
    const all = JSON.parse(fs.readFileSync(path.join(build, "symbols.json"), "utf8"));
    const out = [];
    for (const a of all.assemblies)
        for (const sec of a.sections) {
            if (sec.name !== "Spike" && sec.name !== "Code2") continue;
            for (const [name, v] of Object.entries(sec.labels ?? {})) {
                if (name.includes(".") || name.includes("@")) continue;
                // the generated files' labels count as their file's
                const gen = /gen\/(\w+)\.6502$/.exec(a.sources[v.source] ?? "");
                out.push({ at: v.value, name: gen ? `${gen[1]} (generated)` : name });
            }
        }
    return out.sort((x, y) => x.at - y.at);
}
const profile = new Map();
let samples = 0;
const table = profileEvery ? routines() : [];
function sample(pc) {
    let lo = 0,
        hi = table.length - 1,
        found = "?";
    while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        if (table[mid].at <= pc) {
            found = table[mid].name;
            lo = mid + 1;
        } else hi = mid - 1;
    }
    profile.set(found, (profile.get(found) ?? 0) + 1);
    samples++;
}

async function run(entry, marks = []) {
    if (profileEvery && marks.length) {
        ram[STUB + 2] = entry & 0xff;
        ram[STUB + 3] = entry >> 8;
        cpu.pc = STUB;
        cpu.s = 0xff;
        while (cpu.pc !== STUB_DONE) {
            cpu.execute(profileEvery);
            sample(cpu.pc);
        }
        return marks.map(() => 0).concat([0]);
    }
    ram[STUB + 2] = entry & 0xff;
    ram[STUB + 3] = entry >> 8;
    cpu.pc = STUB;
    cpu.s = 0xff;
    const times = [tm.elapsedCycles];
    for (const m of [...marks, STUB_DONE]) {
        await tm.runUntilAddress(m, 2);
        if (cpu.pc !== m) throw new Error(`didn't reach &${m.toString(16)}: pc &${cpu.pc.toString(16)}`);
        times.push(tm.elapsedCycles);
    }
    return times.slice(1).map((t, i) => t - times[i]);
}

const peek = (a) => ram[a];
const peekw = (a) => ram[a] | (ram[a + 1] << 8);
const pokew = (a, v) => {
    ram[a] = v & 0xff;
    ram[a + 1] = (v >> 8) & 0xff;
};
const signed = (v) => (v & 0x8000 ? v - 0x10000 : v);

// The ST's colours to the screen's bytes, for now: reds colour 1, blues
// and cyans colour 2, white colour 3 (decision 3 leaves the choice open).
const COLOURS = [0x00, 0x0f, 0x0f, 0x0f, 0x0f, 0x0f, 0xf0, 0xf0, 0xf0, 0xf0, 0xf0, 0xf0, 0xf0, 0xf0, 0xf0, 0xff];

await run(need("spike_init"));
const stubCost = (await run(need("spike_done")))[0];

const scenes = JSON.parse(fs.readFileSync(scenesPath, "utf8")).frames;
let [lo, hi] = [0, scenes.length - 1];
if (frameRange) [lo, hi] = frameRange.split("-").map(Number);
// The object table's arrays, and how a record's bytes go into them.
const layout = JSON.parse(fs.readFileSync("build/gen/objects.json", "utf8"));
const arrays = layout.arrays.map((a) => ({ at: need(a.name), st: a.st }));
function putObjects(records) {
    for (let slot = 0; slot < layout.slots; slot++) {
        const rec = records.subarray(64 * slot, 64 * slot + 64);
        if (rec[1] !== 0) throw new Error(`slot ${slot}: type ${rec[0] | (rec[1] << 8)} doesn't fit a byte`);
        for (const a of arrays) ram[a.at + slot] = a.st === null ? 0 : rec[a.st];
    }
}
const word = (lo, hi, slot) => ram[need(lo) + slot] | (ram[need(hi) + slot] << 8);
const out = [];
for (let n = lo; n <= Math.min(hi, scenes.length - 1); n++) {
    const fr = scenes[n];
    putObjects(Buffer.from(fr.objects, "hex"));
    for (const [name, v] of Object.entries(fr.zp)) {
        if (name.startsWith("pl_")) pokew(need(name), v);
        else ram[need(name)] = v & 0xff;
    }
    ram.set(fr.anim, need("anim_frame"));
    ram.set(COLOURS, need("colour_map"));
    // the last frame's lines erased, which must leave the screen empty
    const [erase] = await run(need("spike_erase"));
    let left = 0;
    for (let a = need("SCREEN"); a < 0x8000; a++) if (ram[a]) left++;
    const [camera, lists, objects, done] = await run(need("spike_frame"), [
        need("render_lists"),
        need("render_objects"),
        need("render_done"),
    ]);
    const list = (name, count) => Array.from(ram.subarray(need(name), need(name) + peek(need(count))));
    const coarse = list("coarse_slots", "coarse_n");
    const rel = {};
    const exact = {};
    for (const s of coarse) {
        rel[s] = ["cx", "cy", "cz"].map((f) => signed(word(`ob_${f}_lo`, `ob_${f}_hi`, s)));
        exact[s] = ram[need("ob_exact") + s] !== 0;
    }
    const lines = [];
    const logN = peekw(need("log_n"));
    const logAt = bank(need("BANK_LOG")) + (need("line_log") - 0x8000);
    for (let i = 0, a = logAt; i < Math.min(logN, need("LOG_LINES")); i++, a += need("LOG_ENTRY")) {
        lines.push([ram[a], ram[a + 1], peekw(a + 2), ram[a + 4], peekw(a + 5), ram[a + 7], ram[a + 8]]);
    }
    out.push({
        cycles: { camera, lists, objects, total: camera + lists + objects + done - stubCost, erase: erase - stubCost },
        left,
        coarse,
        near: list("near_slots", "near_n"),
        draw: list("draw_slots", "draw_n"),
        rel,
        exact,
        lines,
        logged: logN,
    });
}
if (profileEvery) {
    const rows = [...profile.entries()].sort((a, b) => b[1] - a[1]);
    for (const [name, n] of rows) console.log(`${((100 * n) / samples).toFixed(1).padStart(5)}%  ${name}`);
}
fs.writeFileSync(outPath, JSON.stringify({ frames: out, first: lo }));
console.log(`${outPath}: ${out.length} frames`);
process.exit(0);
