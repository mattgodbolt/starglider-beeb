// The disc's double buffer: after each erase, the window of the screen
// about to be drawn into must be empty (every line drawn there two frames
// before erased), but for the cells of the texts the panel keeps on that
// screen (src/panel.6502's ps_texts), which it redraws or clears itself.
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
// The panel's texts: each ps_texts bit's (texts_do's tx_first and tx_n), and
// each text's cells, its number's as long as a word's (build/gen/panel.json).
const panel = JSON.parse(fs.readFileSync(path.join(root, "build/gen/panel.json"), "utf8"));
const TEXTS_OF_BIT = [[0], [1], [2], [3], [4], [5, 6], [7, 8, 9], [10, 11, 12]];
const cellsOf = (t) => {
  const [x, y] = panel.places[t.place];
  const n = t.string === "num_text" ? 5 : panel.strings[t.string].length;
  return { x: x + 8 * (t.after ? panel.level_prefix : 0), y, n };
};
function kept(buf, x, y) {
  const bits = ram[sym.ps_texts + buf];                 // (ANDY is at &8000 in jsbeeb's memory)
  for (let b = 0; b < 8; b++)
    if (bits & (1 << b))
      for (const id of TEXTS_OF_BIT[b]) {
        const c = cellsOf(panel.texts[id]);
        if (y >= c.y && y < c.y + 8 && x >= c.x && x < c.x + 8 * c.n) return true;
      }
  return false;
}
await tm.runUntilAddress(sym.start_loaded, 60);     // SG loading the game's files
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
      if (ram[base + a] && !kept(buf, 4 * (sym.WINDOW_COL0 + c), y)) lit++;
    }
  if (lit) { bad++; if (bad < 8) console.log(`frame ${f} buffer ${buf}: ${lit} bytes left, step ${ram[sym.steps] | (ram[sym.steps + 1] << 8)}`); }
}
console.log(`erasecheck: ${frames} frames, ${bad} with something left`);
process.exit(bad ? 1 : 0);
