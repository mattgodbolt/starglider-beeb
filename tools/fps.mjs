// The disc's pace: frames drawn and steps taken a second, over a run of
// emulated time, on jsbeeb's Master.
//
//   node tools/fps.mjs [SECONDS] [KEYS]
//
// It loads build/starglider.ssd's files where !BOOT leaves them (as
// tools/erasecheck.mjs does), runs from start, and reads the engine's
// counters (frames, steps) after fourteen seconds settling (SG loading the
// game's files, then the disc reader's background read) and again at
// the end. KEYS, as tools/listprof.mjs takes them, are held from the end of
// the settling, and the count starts two seconds later, once a turn has
// reached its clamp.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = q;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;
const { loadDisc } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
const word = (a) => ram[a] | (ram[a + 1] << 8);
const read = () => ({ frames: word(sym.frames), steps: word(sym.steps) });
const secs = Number(process.argv[2] ?? 20);
await tm.runFor(14 * 2000000);
const keys = (process.argv[3] ?? "").split(",").filter(Boolean);
for (const k of keys) tm.keyDown(k);
if (keys.length) await tm.runFor(2 * 2000000);
const a = read();
await tm.runFor(secs * 2000000);
const b = read();
const f = (b.frames - a.frames) & 0xffff;
const s = (b.steps - a.steps) & 0xffff;
console.log(`fps: ${(f / secs).toFixed(2)} frames a second, ${(s / secs).toFixed(2)} steps a second, ` +
    `${((50 * secs) / f).toFixed(2)} fields a frame, over ${secs}s${keys.length ? `, holding ${keys.join("+")}` : ""}`);
process.exit(0);
