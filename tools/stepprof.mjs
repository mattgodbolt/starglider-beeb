// Each routine's cycles a step on the disc, calls included, holding keys:
//
//   node tools/stepprof.mjs SECONDS KEYS ROUTINE...
//
// KEYS as tools/listprof.mjs takes them ("" for none). A step is counted at
// each world_lists. A routine at &8000-&BFFF counts only with the world bank
// paged, and a loop back to its own entry isn't a new call.
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
const cpu = tm.processor;
loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
await toGame(tm, sym);
await tm.runFor(4 * 2000000);
const keys = (process.argv[3] ?? "").split(",").filter(Boolean);
for (const k of keys) tm.keyDown(k);
const names = process.argv.slice(4);
const at = new Map();
for (const n of names) {
    if (!(n in sym)) throw new Error(`no ${n}`);
    at.set(sym[n], n);
}
const sums = {}, counts = {};
let steps = 0;
const frames = [];
cpu.debugInstruction.add((pc) => {
    while (frames.length && cpu.s > frames[frames.length - 1].sp) {
        const f = frames.pop();
        sums[f.name] = (sums[f.name] ?? 0) + tm.elapsedCycles - f.t0;
    }
    if (pc === sym.world_lists && (cpu.romsel & 15) === 5) steps++;
    const n = at.get(pc);
    if (n === undefined) return false;
    if (pc >= 0x8000 && pc < 0xc000 && (cpu.romsel & 15) !== 5) return false;
    if (frames.some((f) => f.name === n)) return false;     // a loop back to the entry
    frames.push({ name: n, sp: cpu.s, t0: tm.elapsedCycles });
    counts[n] = (counts[n] ?? 0) + 1;
    return false;
});
const secs = Number(process.argv[2] ?? 10);
await tm.runFor(secs * 2000000);
console.log(`steps ${steps}`);
for (const n of names) console.log(`${n.padEnd(16)} calls/step ${((counts[n] ?? 0) / steps).toFixed(2).padStart(7)}  cycles/step ${Math.round((sums[n] ?? 0) / steps).toString().padStart(7)}  per call ${Math.round((sums[n] ?? 0) / (counts[n] || 1))}`);
