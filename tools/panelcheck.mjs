// Check the panel (src/panel.6502) against the ST's formulas, on jsbeeb's
// Master, frame by frame on captured ST states.
//
//   node tools/panelcheck.mjs [STEPS.json ...] [--build build/spike] [--colours NAME]
//        [--png DIR] [--at CAPTURE:FRAME,...] [--show N] [--quiet]
//
// For each capture (tools/st_steps.py's; all of build/steps by default),
// each frame's ST state where its panel is drawn (the lists point, in
// world_render after the lists; the missile view's render point, as it has
// none) is put into the spike by the map (tools/stput.mjs), with the
// port's own flags as the logic would set them for that frame (world_text,
// kill_shown, level_text, dock_text, mine_text, from the ST's state at the
// points that decide them), and panel_frame draws it into the screen of
// the frame's parity, as the disc alternates them. A model of the ST's
// panel (its waveforms routine and prints, docs/research/st-panel.md) draws
// the same state into two screens of its own, starting from the cockpit,
// in the BBC's colours by the colour option (build/gen/panel.json); each
// frame, the screen drawn is compared with the model's, pixel by pixel,
// the whole of it. --png writes the screens at the frames --at names
// (capture:frame, capture the steps directory's name), the panel's rows
// at 2x; --colours draws with another option's colours (tools/mkpanel.py).
// It prints the cycles panel_frame took, and exits non-zero on any
// difference.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./beeb.mjs";
import { stPut, regionsAt, slotOf } from "./stput.mjs";

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const flag = (name) => (args.includes(name) ? (args.splice(args.indexOf(name), 1), true) : false);
const build = opt("--build", "build/spike");
const colours = opt("--colours", null);
const pngDir = opt("--png", null);
const at = new Set((opt("--at", "") || "").split(",").filter(Boolean));
const show = Number(opt("--show", 3));
const profileEvery = Number(opt("--profile", 0));
const quiet = flag("--quiet");
const trace = flag("--trace");
const captures = args.length
    ? args
    : fs
          .readdirSync("build/steps")
          .map((d) => path.join("build/steps", d, "steps.json"))
          .filter((f) => fs.existsSync(f))
          .sort();

const sym = loadSymbols(path.join(build, "symbols.json"));
const need = (name) => {
    if (!(name in sym)) throw new Error(`no symbol ${name}`);
    return sym[name];
};
const map = JSON.parse(execFileSync("python3", ["-I", "tools/stmap.py", path.join(build, "symbols.json")], { encoding: "utf8" }));
const panel = JSON.parse(fs.readFileSync("build/gen/panel.json", "utf8"));
const cockpit = fs.readFileSync("build/gen/cockpit.bin");
const option = panel.options[colours ?? panel.chosen];
if (!option) throw new Error(`no colour option ${colours}`);

// --- the machine ---
const jsbeeb = path.resolve("node_modules/jsbeeb/src/test-machine.js");
const { TestMachine } = await import(pathToFileURL(jsbeeb).href);
const tm = new TestMachine("Master");
await tm.initialise();
const say = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = say;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const bank = (n) => cpu.romOffset + n * 16384;
const where = (a) => (a >= 0xc000 && a < 0xe000 ? 0x9000 + (a - 0xc000) : a);
const load = (file, addr) => ram.set(fs.readFileSync(path.join(build, file)), addr);
load("SPIKE", need("spike_init"));
load("TABLES", where(need("TABLES")));
load("CODE2", where(need("CODE2")));
load("SHAPES", bank(need("BANK_SHAPES")));
load("WORLD", bank(need("BANK_WORLD")));
load("LOGIC", bank(need("BANK_LOGIC")));
const STUB = 0x0140;
const STUB_DONE = STUB + 6;
async function run(entry) {
    ram.set([0x78, 0xa2, 0, 0x20, entry & 0xff, entry >> 8, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);
    cpu.pc = STUB;
    cpu.s = 0xff;
    const t0 = tm.elapsedCycles;
    await tm.runUntilAddress(STUB_DONE, 5);
    if (cpu.pc !== STUB_DONE) throw new Error(`&${entry.toString(16)} didn't return: pc &${cpu.pc.toString(16)}`);
    return tm.elapsedCycles - t0;
}
async function logic(name) {
    ram[need("logic_bank")] = need("BANK_LOGIC") | need("ROMSEL_ANDY");
    ram[need("logic_call")] = need(name) & 0xff;
    ram[need("logic_call") + 1] = need(name) >> 8;
    if (profileEvery && name === "panel_frame") return sampled(need("spike_logic"));
    return run(need("spike_logic"));
}
// --profile N: the program counter every N cycles of panel_frame, each
// sample to the nearest of the logic bank's routines (labels outside scopes)
const profile = new Map();
const routines = [];
if (profileEvery) {
    const all = JSON.parse(fs.readFileSync(path.join(build, "symbols.json"), "utf8"));
    for (const a of all.assemblies)
        for (const sec of a.sections) {
            if (sec.name !== "LogicBank") continue;
            for (const [n, v] of Object.entries(sec.labels ?? {})) if (!n.includes(".") && !n.includes("@")) routines.push({ at: v.value, name: n });
        }
    routines.sort((x, y) => x.at - y.at);
}
async function sampled(entry) {
    ram.set([0x78, 0xa2, 0, 0x20, entry & 0xff, entry >> 8, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);
    cpu.pc = STUB;
    cpu.s = 0xff;
    const t0 = tm.elapsedCycles;
    while (cpu.pc !== STUB_DONE) {
        cpu.execute(profileEvery);
        const pc = cpu.pc;
        let found = "(elsewhere)";
        if (pc >= 0x8000 && pc < 0xc000) for (const r of routines) if (r.at <= pc) found = r.name;
        profile.set(found, (profile.get(found) ?? 0) + 1);
    }
    return tm.elapsedCycles - t0;
}
// what the frames checked showed
const seen = new Map();
const saw = (what) => seen.set(what, (seen.get(what) ?? 0) + 1);
await run(need("spike_init"));
const stubCost = await run(need("spike_done"));     // (the stub's own; spike_logic's paging stays in)
// another option's colours: its tables over the build's
if (colours) {
    const base = need("panel_colours");
    const masks = panel.masks;
    panel.elements.forEach((e, i) => (ram[bank(need("BANK_LOGIC")) + base - 0x8000 + i] = masks[option.elements[e]]));
    const scan = base + panel.elements.length;
    option.scanner.forEach((c, i) => (ram[bank(need("BANK_LOGIC")) + scan - 0x8000 + i] = masks[c]));
    option.view.forEach((c, i) => (ram[bank(need("BANK_LOGIC")) + scan + 16 - 0x8000 + i] = masks[c]));
}

// --- the screens ---
const SCREEN = need("SCREEN");
const SHADOW = 0x8000;                              // jsbeeb's shadow RAM is at +&8000
const W = 320;
const H = 200;
function pixelsOf(bytes) {
    const out = new Uint8Array(W * H);
    for (let y = 0; y < H; y++)
        for (let x = 0; x < W; x++) {
            const b = bytes[(y >> 3) * 640 + (x >> 2) * 8 + (y & 7)];
            const p = x & 3;
            out[y * W + x] = (((b >> (7 - p)) & 1) << 1) | ((b >> (3 - p)) & 1);
        }
    return out;
}
const screenOf = (s) => pixelsOf(ram.subarray(SCREEN + s * SHADOW, SCREEN + s * SHADOW + 25 * 640));
const cockpitPixels = pixelsOf(cockpit);

// PNG: the BBC's colours, the view's band above row 129, the panel's below.
const RGB = { black: [0, 0, 0], red: [255, 0, 0], cyan: [0, 255, 255], white: [255, 255, 255], blue: [0, 0, 255], green: [0, 255, 0], yellow: [255, 255, 0], magenta: [255, 0, 255] };
const bandsOf = Object.entries(panel.bands).map(([y, names]) => [Number(y), names.map((n) => RGB[n])]);
function png(file, pix, scale = 2) {
    const w = W * scale;
    const h = H * scale;
    const raw = Buffer.alloc((w * 3 + 1) * h);
    for (let y = 0; y < h; y++) {
        const sy = Math.floor(y / scale);
        const band = bandsOf.filter(([b]) => b <= sy).pop()[1];
        raw[y * (w * 3 + 1)] = 0;
        for (let x = 0; x < w; x++) {
            const c = band[pix[sy * W + Math.floor(x / scale)]];
            raw.set(c, y * (w * 3 + 1) + 1 + x * 3);
        }
    }
    const crcTable = Array.from({ length: 256 }, (_, n) => {
        let c = n;
        for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        return c >>> 0;
    });
    const crc = (buf) => {
        let c = 0xffffffff;
        for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
        return (c ^ 0xffffffff) >>> 0;
    };
    const chunk = (type, data) => {
        const len = Buffer.alloc(4);
        len.writeUInt32BE(data.length);
        const td = Buffer.concat([Buffer.from(type), data]);
        const c = Buffer.alloc(4);
        c.writeUInt32BE(crc(td));
        return Buffer.concat([len, td, c]);
    };
    const ihdr = Buffer.alloc(13);
    ihdr.writeUInt32BE(w, 0);
    ihdr.writeUInt32BE(h, 4);
    ihdr[8] = 8;
    ihdr[9] = 2;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]));
}

// --- the ST's state, read from a point's regions ---
const A6 = 0x5bf00;
function stState(r, steps) {
    const vars = r.vars;
    const w = (o) => vars.readUInt16BE(o);
    const s = (o) => vars.readInt16BE(o);
    const b = (o) => vars[o];
    const long = (addr) => {
        for (const [name, start, n] of steps.regions) if (addr >= start && addr + 4 <= start + n) return r[name].readUInt32BE(addr - start);
        throw new Error(`&${addr.toString(16)}`);
    };
    const rec = (slot) => (slot < 140 ? vars.subarray(map.records.offset + 64 * slot) : r.silo.subarray(64 * (slot - 140)));
    const nearN = w(0x240);
    const nearAt = long(A6 + 0x98);
    const near = Array.from({ length: nearN }, (_, k) => {
        const slot = slotOf(map, long(nearAt + 4 * k));
        const o = rec(slot);
        return { slot, type: o.readUInt16BE(0), cx: o.readInt16BE(0x28), cz: o.readInt16BE(0x2c) };
    });
    return {
        x: w(0x12e), y: s(0x130), z: w(0x132), heading: w(0x13c), roll: s(0x13e),
        speed: s(0x21e), shields: w(0x260), energy: w(0x25e), laser: w(0x28a),
        missiles: w(0x278), frameCount: w(0x1e2), refuelling: b(0x2c3), mvRender: b(0x2c9),
        life: s(0x276), iris: s(0x27c), level: w(0x296), near,
        beam: r.beam.readUInt16BE(0) & 0xff, score: [...r.score.subarray(0, 4)],
        docked: b(0x2ca), launch: w(0x292), levelMsg: w(0x298), missileView: b(0x2c8),
        levelChanged: b(0x2d7), gameOver: w(0x12c), kill: w(0x286),
    };
}

// The port's own flags for frame fr, as the logic sets them (src/vars.6502):
// what world_render printed (from the frame's top: world_lists'), the last
// kill before its add, and what the logic after printed: LEVEL (level_message,
// at collide), the docked menu (post_frame, at end), a mine's (the mine
// point's last mine).
function flagsOf(fr, steps) {
    const top = regionsAt(fr, "top");
    const collide = regionsAt(fr, "collide");
    const end = regionsAt(fr, "end");
    if (!top || !collide || !end) return null;
    const t = stState(top, steps);
    let world = 0;
    const open = t.life >= 0x0f && (t.iris === 0 || t.iris === 8);
    if (!t.mvRender && t.docked && t.launch !== 0x1e) world |= 1;
    if (t.launch !== 0 && t.launch !== 0x1e && (!t.mvRender || open)) world |= 2;
    if (t.mvRender && t.life >= 0x0f && t.iris === 0) world |= 8;
    const c = stState(collide, steps);
    const e = stState(end, steps);
    const level = c.levelMsg !== 0 && !c.missileView ? 0xff : 0;
    const dock = !e.levelChanged && !e.gameOver && e.shields !== 0 && e.launch === 0x1e ? 0xff : 0;
    let mine = 0;
    const m = regionsAt(fr, "mine");
    if (m && fr.a0?.mine) {
        const ms = stState(m, steps);
        const slot = slotOf(map, fr.a0.mine);
        const cz = m.vars.readInt16BE(map.records.offset + 64 * slot + 0x2c);
        if (!ms.levelMsg && !ms.docked && !ms.missileView) mine = cz < 0x600 ? 2 : 1;
    }
    return { world, kill: t.kill, level, dock, mine };
}

// --- the model: the ST's panel, in the BBC's colours ---
const E = option.elements;
const SCAN = option.scanner;
const glyphOf = (ch) => panel.font[ch];
class Model {
    constructor() {
        this.buf = [Uint8Array.from(cockpitPixels), Uint8Array.from(cockpitPixels)];
        this.wl = 0;
        this.wr = 0;
        this.dim = 2;
    }
    frame(n, s, f) {
        const px = this.buf[n];
        const set = (x, y, c) => (px[y * W + x] = c);
        const cell = (x, y, ch, c) => {
            const g = glyphOf(ch);
            for (let r = 0; r < 8; r++) for (let i = 0; i < 8; i++) set(x + i, y + r, (g[r] >> (7 - i)) & 1 ? c : 0);
        };
        const text = (x, y, str, c) => [...str].forEach((ch, i) => cell(x + 8 * i, y, ch, c));
        const P = panel.places;
        // waveforms (&05872)
        this.wl = (this.wl + 1) & 15;
        this.wr = (this.wr + 1) & 15;
        for (const [k, [x0, y0]] of [[panel.wave_order.left[this.wl], P.wave_left], [panel.wave_order.right[this.wr], P.wave_right]])
            for (let r = 0; r < 8; r++)
                for (let i = 0; i < 16; i++) set(x0 + i, y0 + r, (panel.waves[k][r][i >> 2] >> (3 - (i & 3))) & 1 ? E.wave : 0);
        if ((s.frameCount & 2) === 0) this.dim ^= 2;
        // altitude (&05994)
        const d = ((-s.y & 0xffff) >> 6) & 31;
        if (d > 28) throw new Error(`altitude ${d}: past what the logic allows`);
        const warn = d < 8 && (s.frameCount & 4) === 0;
        for (let y = 170; y <= 198; y++) {
            const c = y >= 199 - d ? E.alt_low : y >= 171 ? (warn ? E.alt_warn : E.alt_high) : 0;
            for (const x of panel.altitude_x) set(x, y, c);
        }
        // speed (&05A14)
        const v = (s.speed >> 4) & 31;
        for (let y = 171; y <= 198; y++) for (const x of panel.speed_x) set(x, y, y >= 199 - v ? E.speed : 0);
        const notch = (y, key) =>
            panel.speed_x.forEach((x) => {
                const [val] = panel.notch[key][x >> 2 === panel.speed_cols[0] ? 0 : 1];
                const p = x & 3;
                set(x, y, (((val >> (7 - p)) & 1) << 1) | ((val >> (3 - p)) & 1));
            });
        notch(170, v >= 29 ? "170_lit" : "170_unlit");
        notch(169, "169_unlit");
        // bars (&05A4A)
        const bar = (value, [x0, y0], c) => {
            const len = value ? (value >> 11) + 1 : 0;
            for (let y = y0; y < y0 + 4; y++) for (let i = 0; i < 32; i++) set(x0 + i, y, i < len ? c : 0);
            return len;
        };
        bar(s.shields, P.shields, E.bar);
        const elen = s.energy ? (s.energy >> 11) + 1 : 0;
        bar(s.energy, P.energy, elen <= 6 && this.dim ? E.bar_dim : E.bar);
        bar(s.laser, P.laser, E.bar);
        // bank ticks (&05C46)
        const t = (((s.roll >> 1) + 16) & 31);
        for (let y = panel.tick_y; y < panel.tick_y + 4; y++)
            for (const x0 of panel.tick_x) for (let i = 0; i < 32; i++) set(x0 + i, y, i === t ? E.tick : 0);
        // the scanner (&05DB2)
        const [sx, sy] = P.scanner;
        for (let y = sy; y <= sy + 32; y++) for (let x = sx; x < sx + 32; x++) set(x, y, 0);
        set(sx + 16, sy + 16, E.player);
        for (const o of s.near) {
            if (!(o.cx > -0x2000 && o.cx < 0x2000 && o.cz > -0x2000 && o.cz < 0x2000)) continue;
            const x = 160 + (o.cx >> 9);
            const y = 164 + (-o.cz >> 9);
            const c = SCAN[o.type === 11 ? s.beam : panel.types[o.type]];
            px[y * W + x] |= c;
        }
        // the numbers: score and last kill in the normal view; heading,
        // sectors, missiles while the near list isn't empty
        const hex = (v, n) => v.toString(16).toUpperCase().padStart(n, "0");
        if (!s.mvRender) {
            text(P.score[0], P.score[1], s.score.map((b) => hex(b, 2)).join(""), E.score);
            text(P.kill[0], P.kill[1], hex(f.kill, 4), E.kill);
        }
        if (s.near.length) {
            const deg = Math.trunc(((s.heading & 0xfff) << 5) / 365) & 0x1ff;
            text(P.heading[0], P.heading[1], String(deg).padEnd(4, " "), E.heading);
            const letter = deg >= 315 || deg < 45 ? "N" : deg < 135 ? "E" : deg < 225 ? "S" : "W";
            cell(P.heading[0] + 32, P.heading[1], letter, E.compass);
            const sector = (v) => String(Math.floor(v / 0x290) & 0xff).padStart(2, "0");
            text(P.sector_x[0], P.sector_x[1], sector(s.x), E.sector_x);
            text(P.sector_z[0], P.sector_z[1], sector(s.z), E.sector_z);
            text(P.missiles[0], P.missiles[1], String.fromCharCode(48 + (s.missiles & 15)), E.missiles);
        }
        // the texts: the window cleared each frame, as the ST's is
        for (let y = 10; y <= 128; y++) for (let x = 16; x <= 303; x++) set(x, y, 0);
        const cur = s.refuelling ? E.text_15 : s.near.length ? E.text_4 : f.world & 2 ? E.text_15 : E.text_3;
        const S = panel.strings;
        if (f.world & 1) text(...P.docking, S.docking, E.text_15);
        if (f.world & 2) text(...P.launching, S.launching, E.text_15);
        if (s.mvRender && s.life >= 0x0f && s.iris >= 0x11) text(...P.missile_view, S.missile_view, E.text_15);
        if (f.world & 8 && (s.life >= 0x38 || (s.frameCount & 4) === 0)) text(...P.countdown, String(s.life - 0x0f), E.text_4);
        if (!s.mvRender && s.refuelling) text(...P.refuelling, S.refuelling, E.text_15);
        if (f.mine) text(...P.mine, f.mine === 2 ? S.mine_exploded : S.mine_detected, cur);
        if (f.level) {
            text(...P.level, S.level + String(s.level), cur);
            text(...P.manual, S.manual, cur);
        }
        if (f.dock) {
            text(...P.replenished, S.replenished, cur);
            text(...P.press_space, S.press_space, cur);
            text(...P.or_interrogate, S.or_interrogate, cur);
        }
        return px;
    }
}

// --- each capture ---
const put = (steps) => stPut(map, steps, ram);
let failed = 0;
const allCycles = [];
for (const file of captures) {
    const name = path.basename(path.dirname(file));
    const steps = JSON.parse(fs.readFileSync(file, "utf8"));
    const putState = put(steps);
    for (let s = 0; s < 2; s++) ram.set(cockpit, SCREEN + s * SHADOW);
    await logic("panel_init");
    const model = new Model();
    let frames = 0;
    let bad = 0;
    const cycles = [];
    const examples = [];
    for (let n = 0; n < steps.frames.length; n++) {
        const fr = steps.frames[n];
        const point = fr.points.lists ? "lists" : fr.points.render ? "render" : null;
        const flags = point && flagsOf(fr, steps);
        if (!flags) continue;
        const r = regionsAt(fr, point);
        putState(r);
        const st = stState(r, steps);
        const b = frames & 1;
        ram[need("world_text")] = flags.world;
        ram[need("kill_shown")] = flags.kill & 0xff;
        ram[need("kill_shown") + 1] = flags.kill >> 8;
        ram[need("level_text")] = flags.level;
        ram[need("dock_text")] = flags.dock;
        ram[need("mine_text")] = flags.mine;
        ram[need("draw_buffer")] = b;
        ram[need("draw_bank")] = b ? need("ACCCON_X") : 0;
        cycles.push((await logic("panel_frame")) - stubCost);
        const want = model.frame(b, st, flags);
        // (what it showed)
        if (st.mvRender) saw("missile view");
        if (flags.world & 1) saw("DOCKING");
        if (flags.world & 2) saw("LAUNCHING");
        if (flags.world & 8) saw("countdown");
        if (st.mvRender && st.life >= 0x0f && st.iris >= 0x11) saw("MISSILE VIEW");
        if (!st.mvRender && st.refuelling) saw("REFUELLING");
        if (flags.mine) saw(flags.mine === 2 ? "MINE HAS JUST EXPLODED" : "MINE DETECTED");
        if (flags.level) saw("LEVEL");
        if (flags.dock) saw("docked menu");
        if (!st.near.length) saw("near list empty");
        const dots = st.near.filter((o) => o.cx > -0x2000 && o.cx < 0x2000 && o.cz > -0x2000 && o.cz < 0x2000);
        saw(`dots ${Math.min(dots.length, 10)}${dots.length >= 10 ? "+" : ""}`);
        if (dots.some((o) => o.type === 11)) saw("beam dot");
        if (st.energy && (st.energy >> 11) < 6) saw("energy low");
        if (((-st.y & 0xffff) >> 6 & 31) < 8) saw("altitude low");
        if (((st.speed >> 4) & 31) >= 29) saw("speed top");
        if (trace) say(`  ${name} ${n} screen ${b}: ${cycles[cycles.length - 1]} cycles, near ${st.near.length}, dots ${dots.length}, flags ${JSON.stringify(flags)}`);
        const got = screenOf(b);
        frames++;
        let diff = 0;
        for (let i = 0; i < W * H; i++)
            if (got[i] !== want[i]) {
                if (diff < 4 && examples.length < show * 4)
                    examples.push(`frame ${n} screen ${b}: (${i % W},${Math.floor(i / W)}) port ${got[i]} ST ${want[i]}`);
                diff++;
            }
        if (diff) bad++;
        if (at.has(`${name}:${n}`) && pngDir) {
            png(path.join(pngDir, `${name}_${n}${colours ? "_" + colours : ""}.png`), got);
            png(path.join(pngDir, `${name}_${n}_model.png`), want);
        }
    }
    allCycles.push(...cycles);
    const mean = cycles.length ? Math.round(cycles.reduce((a, c) => a + c, 0) / cycles.length) : 0;
    if (!quiet || bad)
        say(`panelcheck ${name}: ${frames} frames, ${bad} differ; cycles mean ${mean}, most ${cycles.length ? Math.max(...cycles) : 0}`);
    for (const e of examples.slice(0, show * 4)) say(`  ${e}`);
    failed += bad;
}
say(`panelcheck: shown ${[...seen].sort().map(([k, v]) => `${k} ${v}`).join(", ")}`);
if (profileEvery) {
    const total = [...profile.values()].reduce((a, c) => a + c, 0);
    for (const [k, v] of [...profile].sort((a, b) => b[1] - a[1]).slice(0, 25)) say(`  ${((100 * v) / total).toFixed(1).padStart(5)}% ${k}`);
}
if (allCycles.length) {
    const sorted = [...allCycles].sort((a, b) => a - b);
    say(`panelcheck: ${allCycles.length} frames; cycles mean ${Math.round(allCycles.reduce((a, c) => a + c, 0) / allCycles.length)}, median ${sorted[sorted.length >> 1]}, 99% ${sorted[Math.floor(sorted.length * 0.99)]}, most ${sorted[sorted.length - 1]}`);
}
process.exit(failed ? 1 : 0);
