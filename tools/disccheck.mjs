// The game's own disc reader (src/disc.6502), on jsbeeb's Master with the
// disc in the drive: SG loads the game's files with it at start (HAZEL's,
// the banks, the cockpit), and then, as the game plays, SHAPES again into
// bank 7, while the logic runs with ANDY paged; each must come out the
// same as the file.
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
const files = ssdFiles(disc);
const word = (a) => ram[a] | (ram[a + 1] << 8);
const t0 = tm.elapsedCycles;
// the start's loads, compared once they're all in, before the code that
// patches itself has run
await tm.runUntilAddress(sym.start_loaded, 60);
const loaded = (tm.elapsedCycles - t0) / 2e6;
const snapshot = Buffer.from(ram);
let t = 0;
while (t < 40) {
    await tm.runFor(500000);
    t += 0.25;
    if (word(sym.frames) > 0 && ram[sym.fdc_state] === 0) break;    // running, and the read done
}
const hazel = (a) => 0x9000 + (a - 0xc000);
const checks = [
    ["TABLES", hazel(sym.TABLES), snapshot],
    ["CODE2", hazel(sym.CODE2), snapshot],
    ["SHAPES", bank(sym.BANK_SHAPES), snapshot],
    ["WORLD", bank(sym.BANK_WORLD), snapshot],
    ["LOGIC", bank(sym.BANK_LOGIC), snapshot],
    ["COCKPIT", sym.SCREEN, snapshot],
    ["SHAPES", bank(sym.BANK_SPARE), ram],              // the background read
];
let bad = 0;
const report = [];
for (const [name, at, mem] of checks) {
    const f = files[name];
    let n = 0;
    for (let i = 0; i < f.length; i++) if (mem[at + i] !== f[i]) n++;
    bad += n;
    report.push(`${name} ${n}`);
}
console.log(`disccheck: the start's loads in ${loaded.toFixed(2)}s, the background read done ${t}s on, ` +
    `${word(sym.frames)} frames drawn; bytes differing: ${report.join(", ")}`);
process.exit(bad ? 1 : 0);
