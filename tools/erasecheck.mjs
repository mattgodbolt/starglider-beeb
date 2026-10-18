// The disc's double buffer: after each erase, the screen about to be drawn
// into must be empty (every line drawn there two frames before erased).
//
//   node tools/erasecheck.mjs [FRAMES]
//
// It runs build/starglider.ssd's program on jsbeeb's Master, its files put
// where !BOOT leaves them, and stops after each erase (models.erased).
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log; console.log = () => {}; await tm.runUntilInput(); console.log = q;
const cpu = tm.processor, ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;
// unpack the disc's files from the .ssd by name
const ssd = fs.readFileSync(path.join(root, "build/starglider.ssd"));
const files = {};
const n = ssd[0x105] / 8;
for (let i = 0; i < n; i++) {
  const name = ssd.subarray(8 + i * 8, 15 + i * 8).toString("latin1").trim();
  const o = 0x108 + i * 8;
  const len = ssd[o + 4] | (ssd[o + 5] << 8) | (((ssd[o + 6] >> 4) & 3) << 16);
  const sector = ssd[o + 7] | ((ssd[o + 6] & 3) << 8);
  files[name] = ssd.subarray(sector * 256, sector * 256 + len);
}
ram.set(files.SG, 0x0e00);
ram.set(files.SHAPES, bank(4));
ram.set(files.WORLD, bank(sym.BANK_WORLD));
ram.set(files.TABLES, 0x5000);
ram.set(files.CODE2, 0x6000);
cpu.pc = sym.start;
const erased = sym["models.erased"];
let bad = 0;
const frames = Number(process.argv[2] ?? 700);
for (let f = 0; f < frames; f++) {
  await tm.runUntilAddress(erased, 2);
  if (cpu.pc !== erased) throw new Error("no erase at frame " + f);
  const buf = ram[sym.model_buffer];
  const base = buf ? 0x8000 : 0;
  let lit = 0;
  for (let a = 0x4180; a < 0x8000; a++) if (ram[base + a]) lit++;
  if (lit && f >= 2) { bad++; if (bad < 8) console.log(`frame ${f} buffer ${buf}: ${lit} bytes left, model ${ram[sym.model_i]} t ${ram[sym.model_t]}`); }
  await tm.runFor(10);
}
console.log(`erasecheck: ${frames} frames, ${bad} with something left`);
process.exit(bad ? 1 : 0);
