// Where world_lists' cycles go on the disc, each step, holding keys:
//
//   node tools/listprof.mjs [SECONDS] [KEYS]
//
// KEYS is a comma-separated list of jsbeeb's key names (KeyboardEvent.code:
// ArrowLeft, Space, KeyX). It prints each part's mean a step: from its
// start to the camera, the camera, the dots, the lists, the coarse list
// and the rotations (to the frame or step_logic). A part in &8000-&BFFF
// counts only with the world bank paged.
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const { loadDisc, toGame } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log; console.log = () => {}; await tm.runUntilInput(); console.log = q;
const cpu = tm.processor, ram = cpu.ramRomOs;
loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
await toGame(tm, sym);
await tm.runFor(4 * 2000000);
const keys = (process.argv[3] ?? "").split(",").filter(Boolean);
for (const k of keys) tm.keyDown(k);
const marks = [
    ["start", sym.world_lists],
    ["camera", sym.camera],
    ["dots", sym.ground_dots],
    ["lists", sym.lists],
    ["make", sym.make_lists],
    ["coarse", sym.coarse_list],
    ["rotate", sym.rotate_lists],
];
const ends = new Set([sym.frame, sym.step_logic]);
const idx = new Map(marks.map(([n, a], i) => [a, i]));
const sums = {}, counts = {};
let cur = null, t0 = 0;
const hook = cpu.debugInstruction.add((pc) => {
    const bank = cpu.romsel & 15;
    const i = idx.get(pc);
    const isEnd = ends.has(pc);
    if (i === undefined && !isEnd) return false;
    if (i !== undefined && pc >= 0x8000 && pc < 0xc000 && bank !== 5) return false;     // another bank's code
    const now = tm.elapsedCycles;
    if (cur !== null) { sums[cur] = (sums[cur] ?? 0) + now - t0; counts[cur] = (counts[cur] ?? 0) + 1; }
    cur = isEnd ? null : marks[i][0]; t0 = now;
    return false;
});
const secs = Number(process.argv[2] ?? 10);
await tm.runFor(secs * 2000000);
for (const k of Object.keys(sums)) console.log(`${k.padEnd(8)} n ${counts[k]} mean ${Math.round(sums[k] / counts[k])}`);
