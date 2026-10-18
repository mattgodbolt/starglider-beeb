// The game's own disc reader (src/disc.6502), on jsbeeb's Master with the
// disc in the drive: SG loads the game's files with it at start (HAZEL's,
// the banks, the cockpit, the loading area's WINDOW and SPEECH), each of
// which must come out the same as the file. Then, as the game plays, the
// harness has it read TABLES again into the loading area's first 4K
// (from engine_run's wait, which steps the read on), while the logic
// runs with ANDY paged and a speech clip plays, its player paging a bank
// for each byte (the third clip, whose bytes are the logic bank's, which
// the read leaves alone), and the read must come out the same too; the clip must keep about its time,
// and the fields their count, with the read's NMIs beside them. What the
// read overwrote is put back.
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
const speech = JSON.parse(fs.readFileSync(path.join(root, "build/gen/speech.json"), "utf8"));
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
// the game running, then from its wait the read, and a clip
while (word(sym.frames) < 2) await tm.runFor(500000);
await tm.runUntilAddress(sym.engine_run, 5);
const area = bank(sym.BANK_PIC);
const kept = Buffer.from(ram.subarray(area, area + 0x1000));
const STUB = 0x0140;
const clip = speech.clips[2];
ram.set([
    0xa2, sym.DF_TABLES, 0xa0, sym.BANK_PIC,                    // LDX #DF_TABLES : LDY #BANK_PIC
    0x9c, sym.fe_dst & 0xff, sym.fe_dst >> 8,                   // STZ fe_dst
    0xa9, 0x80, 0x8d, (sym.fe_dst + 1) & 0xff, (sym.fe_dst + 1) >> 8,   // LDA #&80 : STA fe_dst+1
    0x20, sym.disc_load & 0xff, sym.disc_load >> 8,             // JSR disc_load
    0xa9, 3, 0x8d, sym.sample_clip & 0xff, sym.sample_clip >> 8,                // the third clip
    0xa9, clip.played & 0xff, 0x8d, sym.sample_len & 0xff, sym.sample_len >> 8,
    0xa9, clip.played >> 8, 0x8d, (sym.sample_len + 1) & 0xff, (sym.sample_len + 1) >> 8,
    0x20, sym.speech & 0xff, sym.speech >> 8,                   // JSR speech
    0x4c, sym.engine_run & 0xff, sym.engine_run >> 8,           // JMP engine_run
], STUB);
cpu.pc = STUB;
const r0 = tm.elapsedCycles, f0 = ram[sym.fields];
let spoke = null;                                       // the clip's start, after the read's
const hook = cpu.debugInstruction.add((addr) => {
    if (addr === sym.speech && spoke === null) spoke = tm.elapsedCycles;
    return false;
});
let played = null;
while ((tm.elapsedCycles - r0) / 2e6 < 40) {
    await tm.runFor(played === null ? 1000 : 100000);
    if (played === null && spoke !== null && word(sym.sample_left) === 0) played = (tm.elapsedCycles - spoke) / 2e6;
    if (played !== null && ram[sym.fdc_state] === 0) break;          // the clip over, and the read done
}
hook.remove();
const read = (tm.elapsedCycles - r0) / 2e6;
const fields = (ram[sym.fields] - f0) & 0xff;
const hazel = (a) => 0x9000 + (a - 0xc000);
const checks = [
    ["TABLES", hazel(sym.TABLES), snapshot],
    ["CODE2", hazel(sym.CODE2), snapshot],
    ["SHAPES", bank(sym.BANK_SHAPES), snapshot],
    ["WORLD", bank(sym.BANK_WORLD), snapshot],
    ["LOGIC", bank(sym.BANK_LOGIC), snapshot],
    ["COCKPIT", sym.SCREEN, snapshot],
    ["WINDOW", bank(sym.BANK_PIC) + (sym.WIN_PIC - 0x8000), snapshot],
    ["SPEECH", bank(sym.BANK_PIC), snapshot],
    ["TABLES", area, ram],                              // the read in play
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
ram.set(kept, area);
// the clip's time, at the ST's 6144 bytes a second (and a little more:
// an NMI between the speech tick's reading of T2 and its start of the
// next count delays the count unseen), and the fields'
const want = clip.played / 6144;
if (played === null || played < want - 0.002 || played > want * 1.03) {
    console.log(`disccheck: the clip played in ${played}s, not ${want.toFixed(3)}s`);
    bad++;
}
if (Math.abs(fields - read * 50.08) > 2) {
    console.log(`disccheck: ${fields} fields in ${read.toFixed(2)}s`);
    bad++;
}
console.log(`disccheck: the start's loads in ${loaded.toFixed(2)}s; the read in play done in ${read.toFixed(2)}s, ` +
    `a clip of ${want.toFixed(2)}s played beside it in ${played?.toFixed(3)}s; bytes differing: ${report.join(", ")}`);
process.exit(bad ? 1 : 0);
