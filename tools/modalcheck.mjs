// What holds the step (decision 17) on the disc, on jsbeeb's Master: the
// cheat prompt and Interrogate, each running fields of its own inside
// read_keys, the engine discarding them after (docs/research/st-logic.md,
// "The keys, the commands and the input interrupt").
//
// The cheat prompt: the game held while it waits for its first key; J S
// space A R G twice from a fixed sight and a standstill, the second time
// cheat mode on and the energy, shields and laser filled; a wrong key and
// the keys it swallows; G's wait running out after 1501 fields, as the
// ST's &00BCA does, and no steps after any of it to catch up.
//
// Interrogate: teleported into a silo, DOCKED read over the missile view's
// window picture while docked (src/docked.6502), timed; I at the tunnel's
// end; each entry's texts as the ST's printer has them (tools/
// mkinterrogate.py's data, the panel's colours), a shorter one leaving
// nothing of a longer behind; the frames no closer than INT_FIELDS; E,
// the windows cleared and the docked menu back; then the launch, the
// picture read back, timed, byte for byte WINDOW's, and L's missile view.
//
//   node tools/modalcheck.mjs
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc, toGame, ssdFiles } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const int = JSON.parse(fs.readFileSync(path.join(root, "build/gen/interrogate.json"), "utf8"));
const disc = path.join(root, "build/starglider.ssd");
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = q;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
loadDisc(tm, disc, sym);

const CYCLES = 2000000;
const FIELD = CYCLES / 50;                              // (jsbeeb's, as measured below)
const SHADOW = 0x8000;                                  // (jsbeeb's array keeps shadow RAM there on)
let bad = 0;
const fail = (what) => {
    bad++;
    if (bad <= 20) console.log(`modalcheck: ${what}`);
};
const now = () => tm.elapsedCycles;
const fields = (t) => (now() - t) / FIELD;
const word = (a) => ram[a] | (ram[a + 1] << 8);
const bankByte = (bank, a) => ram[cpu.romOffset + bank * 16384 + (a - 0x8000)];
const run = (s) => tm.runFor(s * CYCLES);
// a BBC key (internal number) pressed and let go, a field's scan apart
const KEY = { DELETE: 0x59, J: 0x45, S: 0x51, SPACE: 0x62, A: 0x41, R: 0x33, G: 0x53, F: 0x43, SLASH: 0x68,
    I: 0x25, E: 0x22, L: 0x56, M: 0x65, P: 0x37, N: 0x55, Q: 0x10 };
const press = async (k, s = 0.1) => {
    cpu.sysvia.keyDownRaw([KEY[k] & 15, KEY[k] >> 4]);
    await run(s);
    cpu.sysvia.keyUpRaw([KEY[k] & 15, KEY[k] >> 4]);
    await run(0.1);
};
const hold = (k, down) => (down ? cpu.sysvia.keyDownRaw : cpu.sysvia.keyUpRaw).call(cpu.sysvia, [KEY[k] & 15, KEY[k] >> 4]);
const until = async (what, test, s = 20) => {
    const t = now();
    while (!test()) {
        if (now() - t > s * CYCLES) {
            fail(`${what}: not within ${s}s`);
            return false;
        }
        await tm.runFor(FIELD);
    }
    return true;
};
// the steps taken; and those in the second after a pause, which with the
// fields it took discarded are the engine's steady rate, a step every
// STEP_FIELDS (with them not, as many as the engine can take to catch up)
const steps = () => word(sym.steps);
const steady = async (what) => {
    const s = steps();
    await run(1);
    const n = steps() - s;
    if (n > Math.ceil(50 / sym.STEP_FIELDS) + 1) fail(`${what}: ${n} steps in the second after, catching up`);
};
const times = {};

await toGame(tm, sym);
{
    const f = ram[sym.fields];
    await tm.runFor(100 * FIELD);
    if (((ram[sym.fields] - f) & 0xff) !== 100) fail(`a field isn't ${FIELD} cycles: ${(ram[sym.fields] - f) & 0xff} in 100`);
}

// --- docked ---
// teleported into a silo's box, as the ST's captures are, at a step's
// start, early in the game, as theirs are; DOCKED read in the tunnel
await tm.runUntilAddress(sym.step_lists, 5);
ram.set([0x30, 0x1c], sym.pl_x);
ram.set([0xd0, 0xff], sym.pl_y);
ram.set([0x60, 0xdc], sym.pl_z);
ram.set([0x10, 0x0c], sym.pl_heading);
await until("docking", () => ram[sym.docked] !== 0, 5);
let t = now();
await until("DOCKED's read", () => ram[sym.ov_have] === sym.OV_DOCKED, 10);
times.docked = (now() - t) / CYCLES;
await until("the tunnel's end", () => word(sym.launch_state) === 0x1e, 20);
await run(0.5);

// --- the cheat prompt ---
// at the tunnel's end, stopped, the sight fixed (F): the toggle wants both
await press("F");
await run(0.5);
if (!ram[sym.sight_fixed] || word(sym.speed_acc)) fail(`F at the tunnel's end: the sight ${ram[sym.sight_fixed]}, the speed &${word(sym.speed_acc).toString(16)}`);
// DELETE: held at its first wait, no step taken however long
await press("DELETE");
let s0 = steps();
await run(3);
if (steps() !== s0) fail(`the prompt's first wait: ${steps() - s0} steps taken while it waited`);
const cheat = async (keys) => {
    for (const k of keys) {
        await press(k);
        await run(0.1);
    }
};
await cheat(["J", "S", "SPACE", "A", "R", "G"]);
await steady("the first entry, its first wait held");
if (ram[sym.cheat_count] !== 1 || ram[sym.cheat_mode]) fail(`the first entry: count ${ram[sym.cheat_count]}, cheat mode ${ram[sym.cheat_mode]}`);
await press("DELETE");
await cheat(["J", "S", "SPACE", "A", "R", "G"]);
await run(0.5);
if (ram[sym.cheat_count] !== 0 || ram[sym.cheat_mode] !== 0xff) fail(`the second entry: count ${ram[sym.cheat_count]}, cheat mode ${ram[sym.cheat_mode]}`);
// (cheat mode's refill each step, post_frame's costs, after the prompt's
// &FFFF; docked, the tunnel's end fills the laser)
if (word(sym.shields) !== 0x9c40 || word(sym.energy) !== 0x55f0) fail(`cheat mode: shields &${word(sym.shields).toString(16)}, energy &${word(sym.energy).toString(16)}`);
// a wrong key third (F for space): four keys more taken, then the game again
await press("DELETE");
await cheat(["J", "S", "F", "L", "P", "M"]);
s0 = steps();
await run(1);
if (steps() !== s0) fail(`a wrong key: the game went on with a key still to take`);
await press("N");
await run(0.5);
if (steps() === s0) fail(`a wrong key: the game held after the keys it swallows`);
if (ram[sym.cheat_mode] !== 0xff || ram[sym.cheat_count] !== 0) fail(`a wrong key changed the cheat: count ${ram[sym.cheat_count]}, mode ${ram[sym.cheat_mode]}`);
if (!ram[sym.sight_fixed]) fail(`a wrong key's F reached the commands`);
// G's wait running out (1501 fields, from R's taken to the timeout), then
// the wait after it: L for it
await press("DELETE");
await cheat(["J", "S", "SPACE", "A"]);
hold("R", true);
await tm.runUntilAddress(sym.wait_key_timeout, 2);
const t0 = now();
hold("R", false);
await tm.runUntilAddress(sym["wait_key_timeout.out"], 40);
times.timeout = fields(t0);
if (Math.abs(times.timeout - sym.KEY_WAIT) > 1) fail(`G's wait ran out after ${times.timeout.toFixed(1)} fields, not ${sym.KEY_WAIT}`);
await run(0.2);
await press("L");
await steady("the timeout");
if (ram[sym.cheat_count] !== 0) fail(`after the timeout: count ${ram[sym.cheat_count]}`);

// --- Interrogate ---
// the texts as the ST's printer makes them on the screen shown
const masks = [1, 3, 2, 2].map((c) => bankByte(sym.BANK_LOGIC, sym.PC_VIEW + c));
const places = ["prompt", "name", "line1", "line2"].map((k) => int.places[k]);
function textCheck(what, entry, longer) {
    const shown = cpu.acccon & 1 ? SHADOW : 0;
    const e = int.entries[entry - 1];
    const strings = [int.prompt, e.name, e.line1, e.line2];
    let wrong = 0;
    strings.forEach((s, l) => {
        const [x, y] = places[l];
        const cells = Math.max(s.length, longer ? longer[l].length : 0);
        for (let c = 0; c < cells; c++) {
            const g = int.font[c < s.length ? s[c] : " "];
            for (let i = 0; i < 16; i++) {
                const col = i >> 3, row = i & 7, yy = y + row;
                const a = sym.SCREEN + (yy >> 3) * 640 + (yy & 7) + ((x >> 2) + 2 * c + col) * 8;
                if (ram[shown + a] !== (g[i] & masks[l])) wrong++;
            }
        }
    });
    if (wrong) fail(`${what}: ${wrong} bytes of its texts not the ST's`);
}
// a frame up: the next made ready, once it's shown (at the vertical sync
// after it's counted)
const shownFrame = async () => {
    const f = word(sym.frames);
    await until("a frame", () => word(sym.frames) !== f, 2);
    await tm.runFor(FIELD + 1000);
    if (ram[sym.frame_ready]) fail("a frame made ready wasn't shown at the next vertical sync");
};
const f0 = word(sym.frames);
press("I");
await until("Interrogate", () => ram[sym.int_entry] === 1, 3);
await shownFrame();
await shownFrame();
textCheck("entry 1", 1);
// its frames' pace: none closer than INT_FIELDS
t = now();
const fa = word(sym.frames);
await run(2);
const pace = fields(t) / (word(sym.frames) - fa);
times.pace = pace;
if (pace < sym.INT_FIELDS - 0.05) fail(`Interrogate's frames ${pace.toFixed(2)} fields apart, under ${sym.INT_FIELDS}`);
// space through the entries: each one's texts, past a longer one's
let entry = 1;
for (let n = 0; n < sym.INT_ENTRIES; n++) {
    const before = int.entries[entry - 1];
    await press("SPACE");
    entry = (entry % sym.INT_ENTRIES) + 1;
    await until(`entry ${entry}`, () => ram[sym.int_entry] === entry, 2);
    // both screens' frames past the change
    await shownFrame();
    await shownFrame();
    textCheck(`entry ${entry}`, entry, [int.prompt, before.name, before.line1, before.line2]);
}
if (entry !== 1) fail(`seventeen spaces: entry ${entry}`);
if (ram[sym.int_type] !== int.entries[0].type) fail(`entry 1's type ${ram[sym.int_type]}`);
times.frames = word(sym.frames) - f0;
s0 = steps();
await press("E");
if (steps() === s0) await run(0.2);
if (steps() === s0) fail("E: the game didn't go on");
await steady("Interrogate");
// the windows clear of Interrogate's texts once each screen's drawn again
{
    let left = 0;
    for (const base of [0, SHADOW])
        for (let l = 0; l < 2; l++) {
            const [x, y] = places[l];
            for (let c = 0; c < 26; c++)
                for (let row = 0; row < 8; row++) {
                    const yy = y + row;
                    const a = sym.SCREEN + (yy >> 3) * 640 + (yy & 7) + ((x >> 2) + 2 * c) * 8;
                    if (ram[base + a] || ram[base + a + 8]) left++;
                }
        }
    if (left) fail(`after E, ${left} bytes of the prompt's and the name's rows not cleared`);
}

// the launch: the picture read back, byte for byte WINDOW's, and L's view
await press("SPACE", 0.5);
t = now();
await until("the launch", () => !ram[sym.docked], 3);
await until("the picture's read", () => ram[sym.ov_have] === sym.OV_FLIGHT && ram[sym.ov_reading] === 0xff, 10);
times.picture = (now() - t) / CYCLES;
const window = ssdFiles(disc).WINDOW;
let diff = 0;
for (let a = sym.WIN_PIC; a < sym.win_pic_end; a++) if (bankByte(sym.BANK_PIC, a) !== window[a - sym.WIN_PIC]) diff++;
if (diff) fail(`the window picture read back: ${diff} bytes not WINDOW's`);
await until("the launch's count", () => word(sym.launch_state) === 0, 10);
await run(0.5);
await press("L");
await until("the missile view", () => ram[sym.missile_view] !== 0, 3);           // (ANDY is at &8000 in jsbeeb's memory)

console.log(`modalcheck: G's wait ran out in ${times.timeout.toFixed(1)} fields; DOCKED read ${times.docked.toFixed(2)}s ` +
    `after docking; Interrogate's frames ${times.pace.toFixed(2)} fields apart (${times.frames} in all); ` +
    `the picture read back ${times.picture.toFixed(2)}s after the launch`);
process.exit(bad ? 1 : 0);
