// The raster as jsbeeb's full video makes it for the disc, booted from its
// !BOOT as a Master boots it (MODE 1, then screen_mode's registers), against
// what the disc and the other checks take it to be (engine.6502):
//
// - the CRTC's registers: a field of FIELD_US, its vertical sync
//   SYNC_TO_TOP lines before the screen's first and VSYNC_LINES long, the
//   System VIA flagging it at its end;
// - the field measured from sync to sync: FIELD_US, the field
//   tools/disc.mjs gives jsbeeb's TestMachine, which has no CRTC;
// - User VIA T1, the palette split's: its time-outs a field apart, each
//   SPLIT_LEAD before the panel's first line (PANEL_LINE) to within T1's
//   own step, the lag of the poll that started it made up for (start.6502's
//   install_irq);
// - the split's four writes: all on the line before the panel's, in its
//   horizontal blank, every field from a game's start (its level flash
//   among them) through play with the laser firing, a turn held and a
//   missile launched, whose speech plays.
//
//   node tools/fieldcheck.mjs
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { MachineSession } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/machine-session.js")).href);
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { fieldCycles } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));

const CYCLES = 2000000;
const US = CYCLES / 1e6;
let bad = 0;
const fail = (what) => {
    bad++;
    if (bad <= 20) console.log(`fieldcheck: ${what}`);
};

const session = new MachineSession("Master");
await session.initialise();
const q = console.log;
console.log = () => {};
session.loadDisc(path.join(root, "build/starglider.ssd"));
await session.autoboot();
console.log = q;
const tm = session._machine;
const cpu = tm.processor;
const video = session._video;
const now = () => tm.elapsedCycles;
await tm.runUntilAddress(sym["front_title.poll"], 60, { bank: sym.BANK_PIC });

// the registers: the 6845's field (R4 + 1 rows of R9 + 1 lines, R5 more,
// half a line more interlaced), its lines R0 + 1 characters of the ULA's
// clock, the sync R7's row on, (R3 >> 4) lines long
const r = video.regs;
const lineCycles = (r[0] + 1) * (video.halfClock ? 2 : 1);
const fieldLines = (r[4] + 1) * (r[9] + 1) + r[5] + (r[8] & 1 ? 0.5 : 0);
const syncToTop = (r[4] + 1 - r[7]) * (r[9] + 1) + r[5];
const vsyncLines = r[3] >> 4 || 16;
if (lineCycles !== sym.SCAN_US * US) fail(`a line of ${lineCycles / US}us, not SCAN_US's ${sym.SCAN_US}`);
if (fieldLines * lineCycles !== sym.FIELD_US * US) fail(`the CRTC's field ${fieldLines} lines, not FIELD_US's ${sym.FIELD_US / sym.SCAN_US}`);
if (syncToTop !== sym.SYNC_TO_TOP) fail(`the sync ${syncToTop} lines before the screen's top, not SYNC_TO_TOP's ${sym.SYNC_TO_TOP}`);
if (vsyncLines !== sym.VSYNC_LINES) fail(`the sync ${vsyncLines} lines long, not VSYNC_LINES's ${sym.VSYNC_LINES}`);
if (cpu.sysvia.pcr & 1) fail("the System VIA flags the sync at its start, not its end");
if (fieldCycles(sym) !== sym.FIELD_US * US) fail(`tools/disc.mjs gives the TestMachine a field of ${fieldCycles(sym)} cycles`);

// The raster's place when something happens: its line on the screen and the
// time to the panel's first line, from the CRTC's counters, less `ahead`
// cycles that the video has run past it.
const place = (ahead = 0) => {
    const line = video.vertCounter * (r[9] + 1) + video.scanlineCounter;
    const h = video.horizCounter;
    return { line, h, toPanel: ((sym.PANEL_LINE - line) * lineCycles - h * (video.halfClock ? 2 : 1) + ahead) / US };
};
// (A VIA's time-out is a task the scheduler runs at its own cycle, in a
// step of the CPU's whose cycles the video has already run: by how many,
// from the CPU's clock against the scheduler's, which keep in step between
// steps, as at each write.)
let clockOff = null;
// the syncs' flags (CA1's falling edge), T1's time-outs and the split's
// writes (irq_handler's, not the flash's), as the game runs
const flags = [];
const setVBlankInt = cpu.sysvia.setVBlankInt;
cpu.sysvia.setVBlankInt = function (level) {
    if (!level) flags.push(now());
    return setVBlankInt.call(this, level);
};
const timeouts = [];
const via = cpu.uservia;
const updateIFR = via.updateIFR;
let t1Was = via.ifr & 0x40;
via.updateIFR = function () {
    const t1 = via.ifr & 0x40;
    if (t1 && !t1Was && clockOff !== null) timeouts.push({ t: cpu.scheduler.epoch, ...place(now() - clockOff - cpu.scheduler.epoch) });
    t1Was = t1;
    return updateIFR.call(this);
};
// (a split shows only where its two sides' colours differ: the front end's
// are the same, and the game's start reads the disc with them)
const SPLIT0 = sym.irq_handler, SPLIT1 = sym["irq_handler.not_split"];
const ram = cpu.ramRomOs;
const shows = () => [0, 1, 2, 3].some((i) => ram[sym.c3_ula + sym.C3_VIEW + i] !== ram[sym.c3_ula + sym.C3_PANEL + i]);
const splits = [];
let writes = [];
cpu.debugWrite.add((addr) => {
    clockOff = now() - cpu.scheduler.epoch;
    if (addr !== sym.ula_pal) return false;
    const pc = cpu.oldPcArray[cpu.oldPcIndex];
    if (pc < SPLIT0 || pc >= SPLIT1) writes = [];
    else if (writes.push(place()) === 4) {
        if (shows()) splits.push(writes);
        writes = [];
    }
    return false;
});

// a game: its start, and play
const press = (k) => cpu.sysvia.keyDownRaw([k & 15, k >> 4]);
const release = (k) => cpu.sysvia.keyUpRaw([k & 15, k >> 4]);
const KEY = { SPACE: 0x62, LEFT: 0x19, L: 0x56, F: 0x43 };
press(KEY.SPACE);
await tm.runFor(0.1 * CYCLES);
release(KEY.SPACE);
await tm.runUntilAddress(sym.engine_run, 60);
await tm.runFor(1 * CYCLES);
press(KEY.LEFT);
for (let i = 0; i < 6; i++) {
    press(KEY.F);
    await tm.runFor(0.3 * CYCLES);
    release(KEY.F);
    await tm.runFor(0.2 * CYCLES);
    if (i === 2) {
        press(KEY.L);
        await tm.runFor(0.1 * CYCLES);
        release(KEY.L);
    }
}
release(KEY.LEFT);
await tm.runFor(2 * CYCLES);

// the field, sync to sync, over all of them (each sync's moment is the
// end of the CPU's step it fell in: a few cycles late)
const gaps = flags.slice(1).map((t, i) => t - flags[i]);
const mean = (flags[flags.length - 1] - flags[0]) / gaps.length;
if (Math.abs(mean - sym.FIELD_US * US) > 1) fail(`the field from sync to sync ${(mean / US).toFixed(2)}us, not ${sym.FIELD_US}`);
const jitter = Math.max(...gaps.map((g) => Math.abs(g - sym.FIELD_US * US)));
if (jitter > 16) fail(`a field from sync to sync ${jitter} cycles out`);
// T1: a field apart, each SPLIT_LEAD before the panel
const apart = timeouts.slice(1).filter((x, i) => x.t - timeouts[i].t !== sym.FIELD_US * US);
if (apart.length) fail(`${apart.length} of T1's time-outs not a field after the last`);
const leads = timeouts.map((x) => x.toPanel);
const lead = [Math.min(...leads), Math.max(...leads)];
if (lead[0] < sym.SPLIT_LEAD - 1 || lead[1] > sym.SPLIT_LEAD + 1)
    fail(`T1 times out ${lead[0]}-${lead[1]}us before the panel's first line, not SPLIT_LEAD's ${sym.SPLIT_LEAD}`);
// the split's writes, in the blank before the panel's line
const blank = [r[1], r[0]];
let outside = 0;
const first = splits.map((w) => w[0].h), last = splits.map((w) => w[3].h);
for (const w of splits)
    if (w.some((p) => p.line !== sym.PANEL_LINE - 1 || p.h < blank[0] || p.h > blank[1])) {
        if (++outside <= 3) fail(`a split's writes at ${w.map((p) => `line ${p.line} character ${p.h}`).join(", ")}`);
    }
if (outside) fail(`${outside} of ${splits.length} splits not in the blank`);
console.log(`fieldcheck: a field of ${fieldLines} lines, ${(mean / US).toFixed(2)}us from sync to sync over ${gaps.length}; ` +
    `T1 ${lead[0]}-${lead[1]}us before the panel's first line, a field apart; ` +
    `${splits.length} splits, their writes from character ${Math.min(...first)}-${Math.max(...first)} to ${Math.min(...last)}-${Math.max(...last)} ` +
    `of the blank's ${blank[0]}-${blank[1]}`);
process.exit(bad ? 1 : 0);
