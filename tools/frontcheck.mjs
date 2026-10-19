// The front end (src/front.6502, src/front_main.6502) on jsbeeb's Master,
// booted from the disc, through the ST's flows (docs/research/st-logic.md,
// "The front end"): the title after the start's loads; the credits after
// its wait, and the title again after theirs; K's screen, six keys
// defined, and the game with them; Esc back to the title; a game over, its
// words, the pilot rating, a high score's name typed, the table, and the
// title after the end screen's wait. Each screen is compared byte for byte
// with what the ST's text printer makes of the ST's texts (tools/mkfront.py's
// build/gen/front.json), the title with the picture as mkfront.py packs it;
// each wait is timed in fields, and each of the disc's loads in seconds.
//
//   node tools/frontcheck.mjs
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const fe = JSON.parse(fs.readFileSync(path.join(root, "build/gen/front.json"), "utf8"));
const panel = JSON.parse(fs.readFileSync(path.join(root, "build/gen/panel.json"), "utf8"));
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
const FIELD = 64 * 312 * 2;                             // (screen_mode's: not interlaced)
const SHADOW = 0x8000;                                  // (jsbeeb's array keeps shadow RAM there on)
const SCREEN = sym.SCREEN, SCREEN_BYTES = 0x8000 - sym.SCREEN;
let bad = 0;
const fail = (what) => {
    bad++;
    console.log(`frontcheck: ${what}`);
};
const now = () => tm.elapsedCycles;
const secs = (t) => (now() - t) / CYCLES;
const fields = (t) => (now() - t) / FIELD;
// (a symbol in a sideways bank is only its own while its bank is paged)
const BANKS = { Front: sym.BANK_PIC, LogicBank: sym.BANK_LOGIC, WorldBank: sym.BANK_WORLD, WindowPic: sym.BANK_PIC };
const bankOf = {};
for (const sec of JSON.parse(fs.readFileSync(path.join(root, "build/starglider.json"), "utf8")).assemblies[0].sections)
    for (const k of Object.keys(sec.labels ?? {})) if (sec.name in BANKS) bankOf[k] = BANKS[sec.name];
const at = async (name, s = 60) => {
    const a = sym[name];
    if (a === undefined) throw new Error(`no symbol ${name}`);
    await tm.runUntilAddress(a, s, name in bankOf ? { bank: bankOf[name] } : {});
};
const press = async (code, s = 0.1) => {
    tm.keyDown(code);
    await tm.runFor(s * CYCLES);
    tm.keyUp(code);
};
// a key held until the symbol's reached (it may come before a press is
// over), and let go
const pressTo = async (code, name, s = 30) => {
    tm.keyDown(code);
    await at(name, s);
    tm.keyUp(code);
};
const bbcPress = async (key, s = 0.1) => {
    cpu.sysvia.keyDownRaw([key & 15, key >> 4]);
    await tm.runFor(s * CYCLES);
    cpu.sysvia.keyUpRaw([key & 15, key >> 4]);
    await tm.runFor(0.1 * CYCLES);
};
const near = (what, got, want, slack) => {
    if (Math.abs(got - want) > slack) fail(`${what}: ${got.toFixed(1)}, not ${want}`);
};

// The ST's printer (&012EC), as front.6502's fe_print draws it: a screen of
// MODE 1's bytes, a cursor, a colour.
class Printer {
    constructor() {
        this.screen = new Uint8Array(SCREEN_BYTES);
        this.col = this.row = 0;
        this.mask = 0xff;
    }
    colour(c) {
        this.mask = fe.masks[c];
    }
    glyph(c) {
        const cell = this.row * 640 + this.col * 16;
        const spread = (n) => n * 0x11;
        for (let r = 0; r < 8; r++) {
            const g = fe.font[(c - 0x20) * 8 + r];
            this.screen[cell + r] = spread(g >> 4) & this.mask;
            this.screen[cell + 8 + r] = spread(g & 15) & this.mask;
        }
    }
    print(bytes) {
        for (const b of bytes) {
            if (b >= 0x80) this.colour(b & 0x7f);
            else if (b === 0x0d) this.col = 0;
            else if (b === 0x0a) this.row = (this.row + 1) % 25;
            else if (b >= 0x20) {
                this.glyph(b);
                if (++this.col === 40) {
                    this.col = 0;
                    this.row = (this.row + 1) % 25;
                }
            }
        }
    }
    text(s) {
        this.print([...s].map((c) => c.charCodeAt(0)));
    }
}
const shown = () => ram.subarray(SHADOW + SCREEN, SHADOW + SCREEN + SCREEN_BYTES);
const same = (what, want) => {
    const got = shown();
    let n = 0, first = -1;
    for (let i = 0; i < SCREEN_BYTES; i++)
        if (got[i] !== want[i]) {
            if (first < 0) first = i;
            n++;
        }
    if (n) {
        const x = ((first % 640) >> 3) * 4, y = ((first / 640) | 0) * 8 + (first & 7);
        fail(`${what}: ${n} bytes of the screen not the ST's, the first at (${x}, ${y}): ` +
            `&${got[first].toString(16)}, not &${want[first].toString(16)}`);
    }
};
// sub_045B4: a long as the ST prints it
const long = (v) => (v === 0 ? "0" : (v >>> 0 >= 0x80000000 ? "M " + (-v >>> 0) : String(v >>> 0)));
const word = (a) => ram[a] | (ram[a + 1] << 8);
const times = {};

// --- the start, and the title ---
let t = now();
await at("start_loaded");
times.start = secs(t);
await at("front_title.pass");
times.title = secs(t);
same("the title", fe.title);

// --- the credits after the title's wait, and the title after theirs ---
t = now();
await at("fe_credits", 40);
near("the title's wait, in fields", fields(t), 0x44c + 1, 3);
await at("front_title.pass");
const credits = new Printer();
credits.colour(15);
credits.print(fe.texts.credits);
same("the credits", credits.screen);
t = now();
await at("fe_title_show", 40);
near("the credits' wait, in fields", fields(t), 0x44c + 1, 3);
t = now();
await at("front_title.pass");
times.show = fields(t);
same("the title again", fe.title);

// --- K: six keys defined (Z, B, H, U, T, V), then Y ---
await pressTo("KeyK", "fe_keys");
const KEYS = [0x61, 0x64, 0x54, 0x35, 0x23, 0x63];
const PROMPTS = ["k_dive", "k_climb", "k_left", "k_right", "k_accel", "k_brake"];
const kscreen = new Printer();
kscreen.print(fe.texts.k_title);
for (let i = 0; i < 6; i++) {
    await tm.runFor(0.2 * CYCLES);
    await bbcPress(KEYS[i]);
    kscreen.print(fe.texts[PROMPTS[i]]);
    const ch = fe.bbc_char[KEYS[i]];
    if (ch) kscreen.print([ch, ...fe.texts.k_echo]);
}
kscreen.print(fe.texts.k_thanks);
await tm.runFor(0.3 * CYCLES);
same("the K screen", kscreen.screen);
await pressTo("KeyY", "game_start", 5);
t = now();
await at("engine_run", 30);
times.started = secs(t);
// the defined keys as the ST's $2D8-$2DD (left, right, dive, climb, accelerate, brake)
const DEF = [2, 3, 0, 1, 4, 5];                         // the prompts' order in def_left's
for (let i = 0; i < 6; i++) {
    const want = fe.bbc_st[KEYS[i]];
    const got = ram[sym.def_left + DEF[i]];
    if (got !== want) fail(`defined key ${PROMPTS[i]}: &${got.toString(16)}, not &${want.toString(16)}`);
}
// H, chosen for Bank Left, banks left in play: the turn's accumulator down
await tm.runFor(1 * CYCLES);
const s16 = (a) => ((word(a) << 16) >> 16);
const x0 = s16(sym.mouse_x);
cpu.sysvia.keyDownRaw([KEYS[2] & 15, KEYS[2] >> 4]);
await tm.runFor(0.5 * CYCLES);
if (ram[sym.key_state + fe.bbc_st[KEYS[2]]] !== 1) fail("the defined Bank Left key's state isn't held");
cpu.sysvia.keyUpRaw([KEYS[2] & 15, KEYS[2] >> 4]);
const x1 = s16(sym.mouse_x);
if (x1 > x0 - 3 * 0x20) fail(`Bank Left held: the turn went from ${x0} to ${x1}`);

// --- Esc: the title ---
await tm.runFor(1 * CYCLES);
await pressTo("Escape", "to_title", 5);
t = now();
await at("front_title.pass", 30);
times.esc = secs(t);
same("the title after Esc", fe.title);

// --- a game from cold, and its end ---
await tm.runFor(8 * CYCLES);
await pressTo("Space", "game_start", 5);
t = now();
await at("engine_run", 30);
times.cold = secs(t);
await tm.runFor(3 * CYCLES);
const counts = [40, 29, 2, 6];
counts.forEach((v, i) => ram.set([v & 255, v >> 8, 0, 0], sym.shots_fired + 4 * i));
ram.set([0x50, 0x21, 0x03, 0x00], sym.score);            // 00032150, which beats the third
ram.set([2, 0], sym.game_over);                          // the shields' end
await at("game_end", 5);
t = now();
await at("panel_game_over", 5);
await at("front_load", 5);
while (ram[sym.fdc_state] === 0) await tm.runFor(1000);
const f0 = now();
while (ram[sym.fdc_state] !== 0) await tm.runFor(1000);
times.endLoad = (now() - f0) / CYCLES;
await at("front_game_over", 30);
times.end = secs(t);
// the words, on the screen shown
{
    const buf = ram[sym.draw_buffer] ? SHADOW : 0;
    const pcol = ram[sym.note_colour];
    const words = "SHIELD DEPLETED,  AGAV DESTROYED!";
    let n = 0;
    for (let i = 0; i < words.length; i++) {
        const rows = panel.font[words[i]];
        for (let r = 0; r < 8; r++) {
            const y = 100 + r, x = 16 + 8 * i;
            const a = SCREEN + (y >> 3) * 640 + (x >> 2) * 8 + (y & 7);
            const spread = (v) => v * 0x11;
            if (ram[buf + a] !== (spread(rows[r] >> 4) & pcol) || ram[buf + a + 8] !== (spread(rows[r] & 15) & pcol)) n++;
        }
    }
    if (n) fail(`the game's end in words: ${n} rows of their glyphs not the ST's`);
}
near("the game's end's wait, in fields", (now() - t) / FIELD, 0x12c + 1, 6);
// the pilot rating: the counts, the accuracy (29 x 100 / 40), the rating
// (the level times it over 100)
await at("fe_wait_key");
const rating = new Printer();
rating.colour(15);
rating.print(fe.texts.r_title);
["r_shots", "r_hits", "r_docks", "r_taken"].forEach((k, i) => {
    rating.print(fe.texts[k]);
    rating.text(long(counts[i]));
});
rating.print(fe.texts.r_newline);
const pct = Math.trunc((counts[1] * 100) / counts[0]) & 255;
rating.print(fe.texts.r_accuracy);
rating.text(long(pct));
rating.print(fe.texts.r_rating);
rating.print(fe.ratings[Math.min(Math.trunc((word(sym.level) * pct) / 100), 11)]);
same("the pilot rating", rating.screen);
// the high score: its place, the name typed
await pressTo("Space", "fe_name", 5);
await tm.runFor(0.3 * CYCLES);
for (const k of ["KeyM", "KeyA", "KeyT", "KeyT"]) {
    await press(k);
    await tm.runFor(0.1 * CYCLES);
}
await press("Enter");
await at("fe_end_wait", 10);
const scores = [], names = [];
for (let i = 0; i < 10; i++) {
    scores.push(ram[sym.hs_scores + 4 * i] | (ram[sym.hs_scores + 4 * i + 1] << 8) | (ram[sym.hs_scores + 4 * i + 2] << 16) | (ram[sym.hs_scores + 4 * i + 3] << 24));
    const nm = [];
    for (let k = 0; k < 9 && ram[sym.hs_names + 9 * i + k]; k++) nm.push(ram[sym.hs_names + 9 * i + k]);
    names.push(nm);
}
const wantScores = [...fe.scores.slice(0, 2), 0x00032150, ...fe.scores.slice(2, 9)];
const wantNames = [...fe.names.slice(0, 2), [..."MATT"].map((c) => c.charCodeAt(0)), ...fe.names.slice(2, 9)];
if (JSON.stringify(scores) !== JSON.stringify(wantScores)) fail(`the high scores: ${scores.map((v) => v.toString(16))}`);
if (JSON.stringify(names) !== JSON.stringify(wantNames)) fail(`the high scores' names: ${JSON.stringify(names)}`);
// the table, and the end screen's boxes round it
const table = new Printer();
table.colour(15);
table.print(fe.texts.h_scores);
for (let i = 0; i < 10; i++) {
    table.print(fe.texts.h_row);
    table.text(wantScores[i].toString(16).padStart(8, "0"));
    table.print(fe.texts.h_gap);
    table.print(wantNames[i]);
}
for (const [col, y0, w, h, fill] of fe.boxes)
    for (let y = y0; y < y0 + h; y++)
        for (let c = col; c < col + w; c++) table.screen[(y >> 3) * 640 + (y & 7) + c * 8] = fill;
same("the high scores and the end screen", table.screen);
t = now();
await at("end_off", 40);
near("the end screen's wait, in fields", fields(t), 0x5dc + 1, 3);
await at("front_title.pass", 10);
same("the title after the game's end", fe.title);
// and a game again, which runs: its frames counted
await pressTo("Space", "game_start", 5);
await at("engine_run", 30);
const frames0 = word(sym.frames);
await tm.runFor(3 * CYCLES);
if (word(sym.frames) - frames0 < 5) fail("the game after the game's end isn't drawing frames");

console.log(`frontcheck: the start's loads ${times.start.toFixed(2)}s, the title up at ${times.title.toFixed(2)}s, ` +
    `shown again (unpacked and faded in) in ${times.show.toFixed(1)} fields; ` +
    `a game's start's loads ${times.started.toFixed(2)}s, ${times.cold.toFixed(2)}s from cold; ` +
    `Esc to the title ${times.esc.toFixed(2)}s; the game's end to the rating ${times.end.toFixed(2)}s, ` +
    `its load ${times.endLoad.toFixed(2)}s of it`);
process.exit(bad ? 1 : 0);
