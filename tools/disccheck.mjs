// The game's own disc reader (src/disc.6502), on jsbeeb's Master with the
// disc in the drive: it reads SHAPES into bank 6 as the models turn, which
// must come out the same as the file, while the game keeps its pace.
//
//   node tools/disccheck.mjs
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc, ssdFiles } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const disc = path.join(root, "build/starglider.ssd");
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = q;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;
loadDisc(tm, disc, sym);
const shapes = ssdFiles(disc).SHAPES;
const at = bank(sym.BANK_SPARE);
ram.fill(0xee, at, at + 16384);
const word = (a) => ram[a] | (ram[a + 1] << 8);
let t = 0;
const second = 2000000;
while (t < 20) {
    await tm.runFor(second / 4);
    t += 0.25;
    if (word(sym.frames) > 0 && ram[sym.fdc_state] === 0) break;    // running, and the read done
}
let bad = 0;
for (let i = 0; i < shapes.length; i++) if (ram[at + i] !== shapes[i]) bad++;
const frames = word(sym.frames);
console.log(`disccheck: SHAPES (${shapes.length} bytes) read in ${t}s, ${bad} bytes differ; ${frames} frames drawn meanwhile`);
process.exit(bad ? 1 : 0);
