// Run the spike's spike_sines in jsbeeb and print what sincos gave at
// every angle, as JSON: [[sine, cosine], ...], each as an unsigned word
// (tools/sinecheck.py compares them with the ST's table).
//
//   node tools/sinerun.mjs [BUILD]
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./beeb.mjs";

const build = process.argv[2] ?? "build/spike";
const jsbeeb = path.resolve("node_modules/jsbeeb/src/test-machine.js");
const { TestMachine } = await import(pathToFileURL(jsbeeb).href);
const sym = loadSymbols(path.join(build, "symbols.json"));
const tm = new TestMachine("Master");
await tm.initialise();
const quiet = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = quiet;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;
const where = (a) => (a >= 0xc000 && a < 0xe000 ? 0x9000 + (a - 0xc000) : a);
const load = (file, at) => ram.set(fs.readFileSync(path.join(build, file)), at);
load("SPIKE", sym.spike_init);
load("TABLES", where(sym.TABLES));
load("CODE2", where(sym.CODE2));
load("SHAPES", bank(sym.BANK_SHAPES));
load("SINE", bank(sym.BANK_SINE));

// The stub: SEI, JSR entry, JMP to itself.
const STUB = 0x0140;
const STUB_DONE = STUB + 4;
async function run(entry) {
    ram.set([0x78, 0x20, entry & 0xff, entry >> 8, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);
    cpu.pc = STUB;
    cpu.s = 0xff;
    await tm.runUntilAddress(STUB_DONE, 30);
    if (cpu.pc !== STUB_DONE) throw new Error(`&${entry.toString(16)} didn't return`);
}
await run(sym.spike_init);
await run(sym.spike_sines);
const at = bank(sym.BANK_LOG) + (sym.LOG - 0x8000);
const word = (a) => ram[a] | (ram[a + 1] << 8);
const out = [];
for (let i = 0; i < 4096; i++) out.push([word(at + 4 * i), word(at + 4 * i + 2)]);
console.log(JSON.stringify(out));
process.exit(0);
