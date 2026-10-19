// The level change's look (src/screen.6502's flash_look, the ST's sub_026B2:
// docs/research/st-logic.md, "The level flash") on jsbeeb's Master, at a
// game's start and at a level change the score forces: every write to the
// ULA's palette, by field and by the screen's line (the game's own model of
// the raster, engine.6502's: line y begins SYNC_TO_TOP + y lines after the
// vertical sync), against the ST's, field by field from V, the field that
// shows the filled window:
//
//   V        the window all logical 3 on the screen shown, colour 0 black;
//   V..V+15  colour 15 strobed white and black, from the window's first
//            line to the split, at about the ST's pace (not.w, 5us a pass);
//   V+16     the same to the ST's line 37, then &555 to the split;
//   V+17..   &444, &333, &222, &111, &000, a field each, each the nearest
//            of white and black (decision 41's midpoint);
//   V+22     colour 15 back, the window white, and init_objects begun.
//
// Below the split the panel's own entry 15 must stand, but for a store of
// the strobe's that the split's interrupt let follow its own, put back
// within STRAY_US.
// Also timed: the fields the level's frame is up before V (the ST's: one),
// and the steps in the second after, which with the pause's fields
// discarded are the engine's steady rate.
//
//   node tools/flashcheck.mjs
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc, toGame } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
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
loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);

const CYCLES = 2000000;
const LINE = 128;                                       // (2MHz cycles, 64us)
const SHADOW = 0x8000;                                  // (jsbeeb's array keeps shadow RAM there on)
let bad = 0;
const fail = (what) => {
    bad++;
    if (bad <= 30) console.log(`flashcheck: ${what}`);
};

// The ST's, measured in Hatari (docs/research/st-logic.md): its strobe's
// whole fields and the line it ends on in the next; the fade's levels from
// there, a VBL each (&555, then -&111); colour 15 back at the VBL after.
const ST_STROBE_FIELDS = 16, ST_STROBE_LINE = 37;
const ST_FADE = [5, 4, 3, 2, 1, 0];
const ST_PASS_US = 5;
// decision 41: no dimmer levels, the colour switching at the midpoint
const nearest = (level) => (level * 2 > 7 ? 7 : 0);
const BLUE = 4, WHITE = 7, BLACK = 0;
// a stray store below the split put back within the strobe's test (two
// passes, the port's) and the put-back's own few microseconds
const STRAY_US = 2 * 10 + 6;

// jsbeeb's TestMachine has no picture, only the vertical sync's pulse, raised
// syncCycles before its field's end: each write's field and line, from it.
const video = cpu.video;
const SYNC = video.fieldCycles - video.syncCycles;
let field = 0, lastSince = 0;
const clock = () => {
    const since = (video.cycles - SYNC + video.fieldCycles) % video.fieldCycles;
    if (since < lastSince) field++;
    lastSince = since;
    return { field, y: since / LINE - sym.SYNC_TO_TOP };
};
// the window's bytes on the screen shown, all logical 3?
const windowFilled = () => {
    const base = cpu.acccon & 1 ? SHADOW : 0;
    const col0 = sym.VIEW_XMIN >> 2, cols = (sym.VIEW_XMAX >> 2) + 1 - col0;
    for (let y = sym.VIEW_YMIN; y <= sym.VIEW_YMAX; y++)
        for (let c = col0; c < col0 + cols; c++)
            if (ram[base + sym.SCREEN + (y >> 3) * 640 + c * 8 + (y & 7)] !== 0xff) return false;
    return true;
};
const writes = [];
const filled = new Map();
const ulaWrite = cpu.ula.write.bind(cpu.ula);
cpu.ula.write = (addr, val) => {
    if ((addr & 3) === 1) {
        const w = { ...clock(), entry: val >> 4, colour: (val & 7) ^ 7 };
        writes.push(w);
        if (w.entry === 15 && w.y > 0 && w.y < sym.PANEL_LINE && !filled.has(w.field)) filled.set(w.field, windowFilled());
    }
    return ulaWrite(addr, val);
};
const marks = [];
cpu.debugInstruction.add((addr) => {
    if (addr === sym.level_flash) marks.push({ what: "flash", ...clock() });
    else if (addr === sym.init_objects && tm.isBankPagedAt(sym.BANK_LOGIC, addr)) marks.push({ what: "init", ...clock() });
    return false;
});
const word = (a) => ram[a] | (ram[a + 1] << 8);

// One level flash: the writes from level_flash's entry to a second past
// init_objects, field by field.
const check = (what, from) => {
    const start = marks.findIndex((m, i) => i >= from && m.what === "flash");
    const init = marks.findIndex((m, i) => i > start && m.what === "init");
    if (start < 0 || init < 0) {
        fail(`${what}: no level flash and init_objects after it`);
        return marks.length;
    }
    const f0 = marks[start].field;
    const byField = (f) => writes.filter((w) => w.field === f);
    const e15 = (f) => byField(f).filter((w) => w.entry === 15);
    // the strobe's fields: the window's lines with colour 15 white and black
    const inWindow = (w) => w.y > sym.VIEW_YMIN - 4 && w.y < sym.PANEL_LINE - 0.5;
    const strobed = (f) => e15(f).filter(inWindow).length > 100;
    let V = f0;
    while (!strobed(V) && V < f0 + 50) V++;
    if (!strobed(V)) {
        fail(`${what}: no strobe within 50 fields`);
        return init + 1;
    }
    const notes = [];
    // the level's frame: its flip (logical 0's entries written) before V
    let flip = V - 1;
    while (flip > f0 - 2 && !byField(flip).some((w) => w.entry === 0)) flip--;
    notes.push(`the level's frame up ${V - Math.max(flip, f0)} fields before V`);
    if (!byField(V).some((w) => w.entry === 0 && w.colour === BLACK && w.y < 0)) fail(`${what}: colour 0 not black at V's flip`);
    if (!filled.get(V)) fail(`${what}: the window shown at V isn't all logical 3`);
    // each field: entry 15's writes in the window's lines, and below the split
    let strays = 0;
    for (let k = 0; k < ST_STROBE_FIELDS + ST_FADE.length; k++) {
        const f = V + k;
        const ws = e15(f);
        const win = ws.filter(inWindow);
        // below the split: the split's own, then nothing but strays and their
        // put-back within STRAY_US of the first
        const split = ws.findIndex((w) => w.colour === BLUE && w.y >= sym.PANEL_LINE - 0.5);
        if (split < 0) fail(`${what}: V+${k}: no split`);
        else {
            const stray = ws.findIndex((w, i) => i > split && w.colour !== BLUE);
            if (stray >= 0) {
                const fix = ws.findIndex((w, i) => i > stray && w.colour === BLUE);
                if (fix < 0 || (ws[fix].y - ws[stray].y) * 64 > STRAY_US || ws.some((w, i) => i > fix && w.colour !== BLUE))
                    fail(`${what}: V+${k}: entry 15 ${ws[stray].colour} at line ${ws[stray].y.toFixed(2)}, below the split, not put back`);
                else strays++;
            }
        }
        if (k < ST_STROBE_FIELDS || k === ST_STROBE_FIELDS) {
            // the strobe: alternating, from the window's top, at about the ST's pace
            const end = k < ST_STROBE_FIELDS ? sym.VIEW_YMAX + 0.5 : ST_STROBE_LINE;
            const strobe = [];
            for (const w of win) {
                if (strobe.length && w.colour === strobe[strobe.length - 1].colour) break;
                strobe.push(w);
            }
            const first = strobe[0], last = strobe[strobe.length - 1];
            if (!first || first.y < sym.VIEW_YMIN - 2 || first.y > sym.VIEW_YMIN + 0.5)
                fail(`${what}: V+${k}: the strobe starts at line ${first?.y.toFixed(2)}`);
            if (!last || Math.abs(last.y - end) > (k < ST_STROBE_FIELDS ? 1.5 : 4))
                fail(`${what}: V+${k}: the strobe ends at line ${last?.y.toFixed(2)}, not ${end}`);
            const us = strobe.slice(1).map((w, i) => (w.y - strobe[i].y) * 64);
            const slow = us.filter((u) => u > 2 * ST_PASS_US).length;
            const mean = us.reduce((a, b) => a + b, 0) / us.length;
            if (mean > 1.4 * ST_PASS_US || slow > us.length / 20)
                fail(`${what}: V+${k}: the strobe's passes ${mean.toFixed(1)}us on average, ${slow} over ${2 * ST_PASS_US}us`);
            if (k === 0) notes.push(`a strobe field ${strobe.length} writes, lines ${first.y.toFixed(1)}-${last.y.toFixed(1)}, ${mean.toFixed(1)}us a pass`);
            if (k === ST_STROBE_FIELDS) {
                // then the &555, the fade's first
                const after = win.filter((w) => w.y > last.y);
                if (!after.length || after.some((w) => w.colour !== nearest(ST_FADE[0])))
                    fail(`${what}: V+${k}: after the strobe, not ${nearest(ST_FADE[0])} (the ST's &555)`);
                notes.push(`the strobe's last field ends at line ${last.y.toFixed(1)} (the ST's ${ST_STROBE_LINE})`);
            }
        } else {
            // the fade's fields: from the window's top, the level's nearest
            const want = nearest(ST_FADE[k - ST_STROBE_FIELDS]);
            const wrong = win.filter((w) => w.colour !== want);
            if (wrong.length) fail(`${what}: V+${k}: colour 15 ${wrong[0].colour} at line ${wrong[0].y.toFixed(2)}, not ${want}`);
            if (want !== WHITE && (!win.length || win[0].y > sym.VIEW_YMIN + 0.5))
                fail(`${what}: V+${k}: the fade's ${want} from line ${win[0]?.y.toFixed(2)}`);
        }
    }
    // V+22: colour 15 back (the vertical sync's own write, nothing in the
    // window) and init_objects begun in that field, as the ST's
    const back = V + ST_STROBE_FIELDS + ST_FADE.length;
    if (e15(back).some(inWindow)) fail(`${what}: V+${back - V}: colour 15 still written in the window`);
    if (marks[init].field !== back) fail(`${what}: init_objects in V+${marks[init].field - V}, not V+${back - V}`);
    notes.push(`${strays} strays below the split, put back`);
    console.log(`flashcheck: ${what}: ${notes.join("; ")}`);
    return init + 1;
};

// the game's start: its first level's (front_main.6502's play)
await toGame(tm, sym);
let next = check("the game's start", 0);
await tm.runFor(2 * CYCLES);
// a level change: the score's ten-thousands moved on, and the level up by one
const level = word(sym.level);
ram[sym.score + 2] = (ram[sym.score + 2] + 1) & 0xff;
await tm.runFor(2 * CYCLES);
next = check("a level change", next);
if (word(sym.level) !== level + 1) fail(`the level ${word(sym.level)}, not ${level + 1}`);
// no steps after it to catch up (decision 17's pauses)
const s0 = word(sym.steps);
await tm.runFor(CYCLES);
const n = word(sym.steps) - s0;
if (n > Math.ceil(50 / sym.STEP_FIELDS) + 1) fail(`${n} steps in the second after, catching up`);
process.exit(bad ? 1 : 0);
