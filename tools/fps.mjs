// The disc's pace: frames drawn and steps taken a second, over a run of
// emulated time, on jsbeeb's Master.
//
//   node tools/fps.mjs [SECONDS]
//
// It loads build/starglider.ssd's files where !BOOT leaves them (as
// tools/erasecheck.mjs does), runs from start, and reads the engine's
// counters (frames, steps, fields) after a second's settling and again at
// the end.
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
const ssd = fs.readFileSync(path.join(root, "build/starglider.ssd"));
const files = {};
for (let i = 0; i < ssd[0x105] / 8; i++) {
    const name = ssd.subarray(8 + i * 8, 15 + i * 8).toString("latin1").trim();
    const o = 0x108 + i * 8;
    const len = ssd[o + 4] | (ssd[o + 5] << 8) | (((ssd[o + 6] >> 4) & 3) << 16);
    const sector = ssd[o + 7] | ((ssd[o + 6] & 3) << 8);
    files[name] = ssd.subarray(sector * 256, sector * 256 + len);
}
ram.set(files.SG, 0x0e00);
ram.set(files.SHAPES, bank(sym.BANK_SHAPES));
ram.set(files.WORLD, bank(sym.BANK_WORLD));
ram.set(files.TABLES, 0x5000);
ram.set(files.CODE2, 0x6000);
cpu.pc = sym.start;
const word = (a) => ram[a] | (ram[a + 1] << 8);
const read = () => ({ frames: word(sym.frames), steps: word(sym.steps) });
const secs = Number(process.argv[2] ?? 20);
await tm.runFor(2000000);
const a = read();
await tm.runFor(secs * 2000000);
const b = read();
const f = (b.frames - a.frames) & 0xffff;
const s = (b.steps - a.steps) & 0xffff;
console.log(`fps: ${(f / secs).toFixed(2)} frames a second, ${(s / secs).toFixed(2)} steps a second, ` +
    `${((50 * secs) / f).toFixed(2)} fields a frame, over ${secs}s`);
process.exit(0);
