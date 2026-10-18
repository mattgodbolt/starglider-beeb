// Run scenes through the port's renderer on jsbeeb's Master, and record
// what it makes of them and how long each part takes.
//
//   node tools/scenerun.mjs SCENES.json OUT.json [--build build/spike] [--frames A-B]
//
// SCENES.json is tools/mkscene.py's: each frame's objects, inputs and
// animation frames. The build directory holds the spike's binaries
// (SPIKE, SHAPES, SINE) and its symbols.json. Each frame is written into
// memory, spike_frame is called from a stub with interrupts off, and the
// cycles are jsbeeb's own count between the phases' labels (render,
// render_lists, render_objects, render_done). tools/scenecheck.py
// compares OUT.json with the ST's renderer.
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

const load = (file, at) => {
    const data = fs.readFileSync(path.join(build, file));
    ram.set(data, at);
};
load("SPIKE", need("spike_init"));
load("SHAPES", bank(need("BANK_SHAPES")));
load("SINE", bank(need("BANK_SINE")));

// The stub: SEI, JSR entry, JMP to itself.
const STUB = 0x0140;
const STUB_DONE = STUB + 4;
ram.set([0x78, 0x20, 0, 0, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);

async function run(entry, marks = []) {
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
const objBank = bank(need("BANK_OBJECTS")) + (need("OBJECTS") - 0x8000);
const OB = { cx: 0x28 };
const out = [];
for (let n = lo; n <= Math.min(hi, scenes.length - 1); n++) {
    const fr = scenes[n];
    ram.set(Buffer.from(fr.objects, "hex"), objBank);
    for (const [name, v] of Object.entries(fr.zp)) {
        if (name.startsWith("pl_")) pokew(need(name), v);
        else ram[need(name)] = v & 0xff;
    }
    ram.set(fr.anim, need("anim_frame"));
    ram.set(COLOURS, need("colour_map"));
    const [camera, lists, objects, done] = await run(need("spike_frame"), [
        need("render_lists"),
        need("render_objects"),
        need("render_done"),
    ]);
    const list = (name, count) => Array.from(ram.subarray(need(name), need(name) + peek(need(count))));
    const coarse = list("coarse_slots", "coarse_n");
    const rel = {};
    for (const s of coarse) {
        const r = objBank + s * 64 + OB.cx;
        rel[s] = [signed(peekw(r)), signed(peekw(r + 2)), signed(peekw(r + 4))];
    }
    const lines = [];
    const logN = peekw(need("log_n"));
    for (let i = 0, a = need("line_log"); i < Math.min(logN, need("LOG_LINES")); i++, a += need("LOG_ENTRY")) {
        lines.push([ram[a], ram[a + 1], peekw(a + 2), ram[a + 4], peekw(a + 5), ram[a + 7], ram[a + 8]]);
    }
    out.push({
        cycles: { camera, lists, objects, total: camera + lists + objects + done - stubCost },
        coarse,
        near: list("near_slots", "near_n"),
        draw: list("draw_slots", "draw_n"),
        rel,
        lines,
        logged: logN,
    });
}
fs.writeFileSync(outPath, JSON.stringify({ frames: out, first: lo }));
console.log(`${outPath}: ${out.length} frames`);
process.exit(0);
