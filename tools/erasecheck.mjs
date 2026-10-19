// The disc's double buffer: after each erase, the window of the screen
// about to be drawn into must be empty (every line drawn there two frames
// before erased), but for the cells of the texts the panel keeps on that
// screen (src/panel.6502's ps_texts), which it redraws or clears itself.
// A missile is launched and steered (L, then the cursor keys), and in its
// view the window, once drawn (under_draw's win_draw), must be the ST's
// (&06B7E: the picture's rows 10 to 130 from 10 + m_iris on, cleared below,
// and the bar's blocks when it's open), every line drawn over it erased and
// what they took put back, but for the texts' cells.
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
const { loadDisc, toGame } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
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
// the window as the ST copies it in the missile view, by screen offset
// (tools/mkcockpit.py's picture, unpacked)
const winRaw = fs.readFileSync(path.join(root, "build/gen/window.raw"));
const PIX = [0x88, 0x44, 0x22, 0x11];
const at = (x, y) => sym.SCREEN + (y >> 3) * 640 + (x >> 2) * 8 + (y & 7);
function stWindow(iris, life) {
  const want = new Map();
  for (let y = 10; y <= 130; y++)
    for (let x = sym.VIEW_XMIN; x <= sym.VIEW_XMAX; x += 4) {
      const r = y + iris;
      want.set(at(x, y), r <= 130 ? winRaw[((r >> 3) - 1) * 576 + ((x - sym.VIEW_XMIN) >> 2) * 8 + (r & 7)] : 0);
    }
  if (iris === 0) {
    const blocks = 17 - ((((life - 0xf) << 16) >> 20) & 0xf);
    let x = 0xd3;
    for (let b = 0; b < blocks; b++) {
      for (let px = x - 2; px <= x + 1; px++)
        for (let y = 0x76; y < 0x7a; y++) want.set(at(px, y), want.get(at(px, y)) | (PIX[px & 3] & ram[sym.colour_map + 7]));
      x -= 6;
      if (b + 1 === 8 || b + 1 === 9) x -= 2;
    }
  }
  return want;
}
const MISSILE_AT = 150;
const KEYS = [[MISSILE_AT, "KeyL", true], [MISSILE_AT + 4, "KeyL", false], [MISSILE_AT + 30, "ArrowLeft", true],
  [MISSILE_AT + 90, "ArrowLeft", false], [MISSILE_AT + 100, "ArrowRight", true], [MISSILE_AT + 160, "ArrowRight", false]];
const drawn = sym.moving + 3;                       // (under_draw's JMP dots_draw, the window drawn)
await toGame(tm, sym);                              // SG loading the game's files, the title, a game
ram[sym.cheat_mode] = 0xff;                         // (its refills: the game mustn't end, for the front end)
let bad = 0, mvFrames = 0, mvBad = 0, mvLines = 0;
const frames = Number(process.argv[2] ?? 700);
for (let f = 0; f < frames; f++) {
  for (const [at_, key, down] of KEYS) if (at_ === f) (down ? tm.keyDown(key) : tm.keyUp(key));
  await tm.runUntilAddress(erased, 2);
  if (cpu.pc !== erased) throw new Error("no erase at frame " + f);
  const buf = ram[sym.draw_buffer];
  const base = buf ? 0x8000 : 0;
  if (ram[sym.mv_render]) {
    if (ram[sym.win_shown + buf] === 0) mvLines += sym.ERASE_LINES - ram[sym.erase_stop + buf];   // (the open window's last frame's)
    await tm.runUntilAddress(drawn, 2, { bank: sym.BANK_PIC });
    mvFrames++;
    const want = stWindow(ram[sym.m_iris], ram[sym.m_life] | (ram[sym.m_life + 1] << 8));
    let wrong = 0;
    for (const [a, v] of want) {
      const x = sym.VIEW_XMIN + (((a - sym.SCREEN) % 640) >> 3) * 4, y = (((a - sym.SCREEN) / 640) | 0) * 8 + ((a - sym.SCREEN) & 7);
      if (ram[base + a] !== v && !kept(buf, x, y)) wrong++;
    }
    if (wrong) { mvBad++; if (mvBad < 8) console.log(`frame ${f} buffer ${buf}: the missile view's window at m_iris ${ram[sym.m_iris]}: ${wrong} bytes not the ST's`); }
    continue;
  }
  if (ram[sym.win_shown + buf] !== 0xff) continue;    // (the window shown on it last: cleared next)
  // the window (src/cockpit.6502), all that's drawn in or cleared
  let lit = 0;
  for (let y = sym.VIEW_YMIN; y <= sym.VIEW_YMAX; y++)
    for (let c = 0; c < sym.WINDOW_COLS; c++) {
      const a = sym.SCREEN + (y >> 3) * 640 + (y & 7) + (sym.WINDOW_COL0 + c) * 8;
      if (ram[base + a] && !kept(buf, 4 * (sym.WINDOW_COL0 + c), y)) lit++;
    }
  if (lit) { bad++; if (bad < 8) console.log(`frame ${f} buffer ${buf}: ${lit} bytes left, step ${ram[sym.steps] | (ram[sym.steps + 1] << 8)}`); }
}
console.log(`erasecheck: ${frames} frames, ${bad} with something left; ${mvFrames} of the missile view, ${mvBad} windows not the ST's, ${mvLines} lines and boxes erased from them`);

// Row 130, the window's last, black on both screens after the missile view,
// as the ST leaves it for the rest of the game (docs/research/st-panel.md,
// section 8); and the cockpit's again on both at the next game's start, as
// the ST's sub_039B2 copies the picture to both screens.
const cockpit = fs.readFileSync(path.join(root, "build/gen/cockpit.bin"));
const row130 = (base) => {
  let lit = 0, wrong = 0;
  for (let c = sym.WINDOW_COL0; c < sym.WINDOW_COL0 + sym.WINDOW_COLS; c++) {
    const o = (130 >> 3) * 640 + c * 8 + (130 & 7);
    if (ram[base + sym.SCREEN + o]) lit++;
    if (ram[base + sym.SCREEN + o] !== cockpit[o]) wrong++;
  }
  return { lit, wrong };
};
let rowBad = 0;
for (const base of [0, 0x8000])
  if (row130(base).lit) { rowBad++; console.log(`erasecheck: after the missile view, row 130 isn't black on the ${base ? "shadow" : "main RAM's"} screen`); }
tm.keyDown("Escape");
await tm.runFor(0.1 * 2000000);
tm.keyUp("Escape");
await toGame(tm, sym);
for (const base of [0, 0x8000]) {
  const { wrong } = row130(base);
  if (wrong) { rowBad++; console.log(`erasecheck: at the next game's start, row 130 on the ${base ? "shadow" : "main RAM's"} screen: ${wrong} bytes not the cockpit's`); }
}
if (!rowBad) console.log("erasecheck: row 130 black after the missile view, the cockpit's again at the next game's start");
process.exit(bad || mvBad || !mvFrames || rowBad ? 1 : 0);
