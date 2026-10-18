// The disc's double buffer: after each erase, the window of the screen
// about to be drawn into must be empty (every line drawn there two frames
// before erased).
//
//   node tools/erasecheck.mjs [FRAMES]
//
// It runs build/starglider.ssd's program on jsbeeb's Master, its files put
// where !BOOT leaves them, and stops after each erase (frame.erased).
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
const { loadDisc } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
const erased = sym["frame.erased"];
let bad = 0;
const frames = Number(process.argv[2] ?? 700);
for (let f = 0; f < frames; f++) {
  await tm.runUntilAddress(erased, 2);
  if (cpu.pc !== erased) throw new Error("no erase at frame " + f);
  const buf = ram[sym.draw_buffer];
  const base = buf ? 0x8000 : 0;
  // the window (src/cockpit.6502), all that's drawn in or cleared
  let lit = 0;
  for (let y = sym.VIEW_YMIN; y <= sym.VIEW_YMAX; y++)
    for (let c = 0; c < sym.WINDOW_COLS; c++) {
      const a = sym.SCREEN + (y >> 3) * 640 + (y & 7) + (sym.WINDOW_COL0 + c) * 8;
      if (ram[base + a]) lit++;
    }
  if (lit) { bad++; if (bad < 8) console.log(`frame ${f} buffer ${buf}: ${lit} bytes left, model ${ram[sym.model_i]} t ${ram[sym.model_t]}`); }
}
console.log(`erasecheck: ${frames} frames, ${bad} with something left`);
process.exit(bad ? 1 : 0);
