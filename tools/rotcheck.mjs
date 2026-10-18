// The rotations checked whole (decision 11): rotate_setup, rotate_exact and
// rotate_approx on the spike's build, against tools/rotcases.py's cases.
//
//   node tools/rotcheck.mjs CASES.json
//
// Each matrix is set up after the last, so only what changed is patched and
// links are remade when an entry's kind or sign changes, as in a turn; each
// offset is rotated both ways and compared, bit for bit, with the ST's exact
// rotation and the model of the approximation.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const build = "build/spike";
const sym = loadSymbols(path.join(build, "symbols.json"));
const need = (n) => {
    if (!(n in sym)) throw new Error(`no ${n}`);
    return sym[n];
};
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log; console.log = () => {}; await tm.runUntilInput(); console.log = q;
const cpu = tm.processor, ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;
const where = (a) => (a >= 0xc000 && a < 0xe000 ? 0x9000 + (a - 0xc000) : a);
const load = (file, at) => ram.set(fs.readFileSync(path.join(build, file)), at);
load("SPIKE", need("spike_init"));
load("TABLES", where(need("TABLES")));
load("CODE2", where(need("CODE2")));
load("SHAPES", bank(need("BANK_SHAPES")));
load("WORLD", bank(need("BANK_WORLD")));
const STUB = 0x0140, DONE = STUB + 8;
async function call(entry, until = DONE, jump = false) {
    // SEI; LDA #bank; STA romsel; JSR/JMP entry; JMP self
    ram.set([0x78, 0xa9, need("BANK_WORLD"), 0x8d, need("romsel") & 0xff, need("romsel") >> 8,
        jump ? 0x4c : 0x20, entry & 0xff, entry >> 8, 0x4c, (STUB + 9) & 0xff, (STUB + 9) >> 8], STUB);
    cpu.pc = STUB;
    cpu.s = 0xff;
    await tm.runUntilAddress(until, 2);
    if (cpu.pc !== until) throw new Error(`&${entry.toString(16)}: stopped at &${cpu.pc.toString(16)}`);
}
await call(need("spike_init"), STUB + 9);
const pokew = (a, v) => { cpu.writemem(a, v & 0xff); cpu.writemem(a + 1, (v >> 8) & 0xff); };
const peekw = (a) => { const v = cpu.readmem(a) | (cpu.readmem(a + 1) << 8); return v & 0x8000 ? v - 0x10000 : v; };
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let bad = 0, n = 0;
for (const [ci, c] of cases.entries()) {
    for (let i = 0; i < 9; i++) pokew(need("cam") + 2 * i, c.cam[i]);
    await call(need("rotate_setup"), STUB + 9);
    for (const t of c.ds) {
        for (let j = 0; j < 3; j++) pokew(need("rot_d") + 2 * j, t.d[j]);
        await call(need("rotate_exact"), STUB + 9);
        const ex = [0, 1, 2].map((j) => peekw(need("rot_acc") + 2 * j));
        for (let j = 0; j < 3; j++) pokew(need("rot_d") + 2 * j, t.d[j]);
        await call(need("rotate_approx"), need("rotate_lists.relevance"), true);
        const ap = [peekw(need("rot_acc")), peekw(need("rot_acc") + 4)];
        n++;
        if (ex.join() !== t.exact.join() || ap.join() !== t.approx.join()) {
            if (bad++ < 8) console.log(`matrix ${ci} ${c.cam} d ${t.d}: exact ${ex} want ${t.exact}; approx ${ap} want ${t.approx}`);
        }
    }
}
console.log(`rotcheck: ${cases.length} matrices, ${n} offsets, ${bad} differ`);
process.exit(bad ? 1 : 0);
