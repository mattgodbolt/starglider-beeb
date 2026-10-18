// Check the view's drawing besides the objects (src/view.6502) against the
// ST's, on the logic's captures (tools/st_steps.py), on jsbeeb's Master.
//
//   node tools/viewrun.mjs STEPS.json... [--build build/spike] [--show N] [--cycles]
//   node tools/viewrun.mjs --scenes SCENES.json     the shots' formula against
//                                                   the ST's own lines
//
// For each frame of each capture, the ST's state is put into the port by
// the map tools/logicrun.mjs uses (tools/stmap.py, build/gen/objects.json):
//
// - the gunsight and the ground dots: from `top`, spike_under runs
//   world_lists (whose ground_dots tells the drawing which dots it kept in
//   view) and draws them onto the cockpit in main RAM's screen, which is
//   read back. The sight's pixels must be the ST's bitmap (STAR.PRG's
//   D_0732A) at the sight; the dots' must be where the ST's &047AA plots
//   them, run here on the captured state (top's dots, the camera matrix at
//   `lists`, the 68000's arithmetic), within a pixel. A dot this model
//   finds in view must be where it was at `lists` and one it finds outside
//   must have moved (been put back ahead), which checks the model itself.
//   Then the frame is erased from its erase list, and the cockpit must be
//   all that's left.
// - in the missile view (whose frames have no `lists`: `render` stands in)
//   the window: the whole screen must be the cockpit with the picture's
//   window rows slid by m_iris, cleared below, and the bar on it when it's
//   open (&06B7E, L_052EC: tools/mkcockpit.py's picture); and again, the
//   same, once erased and put back as an open window is. The dots over it
//   are checked where they change the picture. A frame after the missile
//   view, drawn over the open window, must clear it.
// - the bolt: from `lists`, world_after, then spike_over: the bolt's lines
//   (slot VIEW_BOLT in the line log) must be the ST's (&087FA) for the
//   state at `render`, cut to the window by &0A170's arithmetic.
// - the shots: from `flight`, object_handlers, then spike_over: the
//   shots' lines (VIEW_SHOT) must be as many as the ST's (its random32
//   calls from &07E9E), each end the ST's (its random numbers replayed from
//   the state at `flight`, checked against the state at `handlers`), each
//   start the projected gun (&07E6E) of an object the ST had drawn.
//
// --scenes checks the shots' formula itself on a scene capture
// (tools/st_scenes.py), whose frames hold the ST's own lines: each red line
// after the objects must be some drawn object's gun to some x on the
// window's bottom edge, cut to the window.
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./beeb.mjs";

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const flag = (name) => {
    const i = args.indexOf(name);
    if (i < 0) return false;
    args.splice(i, 1);
    return true;
};
const build = opt("--build", "build/spike");
const show = Number(opt("--show", 3));
const scenesPath = opt("--scenes", null);
const wantCycles = flag("--cycles");

// ---------------------------------------------------------------------------
// The ST's arithmetic and the models.
const w16 = (x) => {
    x &= 0xffff;
    return x & 0x8000 ? x - 0x10000 : x;
};
const l32 = (x) => {
    x = Number(BigInt.asIntN(32, BigInt(Math.trunc(x))));
    return x;
};
const fmul = (m, d) => w16(Math.floor((w16(m) * w16(d)) / 16384));     // muls; asl.l #2; swap
// divs.w: the quotient truncated towards zero, or null on overflow
function divs(dividend, divisor) {
    dividend = l32(dividend);
    divisor = w16(divisor);
    let q = Math.trunc(Math.abs(dividend) / Math.abs(divisor));
    if (dividend < 0 !== divisor < 0) q = -q;
    return q >= -0x8000 && q <= 0x7fff ? q : null;
}
// x << 7 divs z, its low word on an overflow (as divs leaves the operand)
const proj = (x, z) => {
    const n = l32(w16(x) * 128);
    const q = divs(n, z);
    return w16(q === null ? n : q);
};

const VIEW = { xmin: 16, xmax: 303, ymin: 10, ymax: 128 };
const MISSILE_VIEW = { xmin: 0x50, xmax: 0xef, ymin: 0x10, ymax: 0x70 };

// &0A170: Cohen-Sutherland to the window, as tools/st_render.py has it.
function clip2d(line, win = VIEW) {
    let [x0, y0, x1, y1] = line;
    const { xmin, xmax, ymin, ymax } = win;
    const code = (x, y) => (x > xmax ? 8 : 0) | (y > ymax ? 4 : 0) | (x < xmin ? 2 : 0) | (y < ymin ? 1 : 0);
    const cut = (a, b, c, d) => {
        const prod = w16(b) * w16(c);
        const q = divs(prod, d);
        return w16(a + (q === null ? prod : q));
    };
    for (let guard = 0; guard < 64; guard++) {
        let c0 = code(x0, y0),
            c1 = code(x1, y1);
        if (!(c0 | c1)) return [x0, y0, x1, y1];
        if (c0 & c1) return null;
        if (x1 === x0) {
            if (y0 < ymin || y0 > ymax) y0 = Math.min(Math.max(y0, ymin), ymax);
            if (y1 < ymin || y1 > ymax) y1 = Math.min(Math.max(y1, ymin), ymax);
            continue;
        }
        if (y1 === y0) {
            if (x0 < xmin || x0 > xmax) x0 = Math.min(Math.max(x0, xmin), xmax);
            if (x1 < xmin || x1 > xmax) x1 = Math.min(Math.max(x1, xmin), xmax);
            continue;
        }
        if (c0 === 0) {
            [x0, y0, x1, y1] = [x1, y1, x0, y0];
            [c0, c1] = [c1, c0];
        }
        if (c0 & 1) [x0, y0] = [cut(x0, w16(ymin - y0), w16(x1 - x0), w16(y1 - y0)), ymin];
        else if (c0 & 2) [x0, y0] = [xmin, cut(y0, w16(xmin - x0), w16(y1 - y0), w16(x1 - x0))];
        else if (c0 & 4) [x0, y0] = [cut(x0, w16(ymax - y0), w16(x1 - x0), w16(y1 - y0)), ymax];
        else [x0, y0] = [xmax, cut(y0, w16(xmax - x0), w16(y1 - y0), w16(x1 - x0))];
    }
    throw new Error(`clip didn't settle: ${line}`);
}

// A capture's state at a point: the ST's memory as the ST addresses it.
function stMemory(regions, point) {
    const blocks = Object.entries(point).map(([name, hex]) => {
        const [, start] = regions.find(([n]) => n === name);
        return { start, data: Buffer.from(hex, "hex") };
    });
    const u8 = (a) => {
        for (const b of blocks) if (a >= b.start && a < b.start + b.data.length) return b.data[a - b.start];
        throw new Error(`&${a.toString(16)} not captured`);
    };
    const u16 = (a) => (u8(a) << 8) | u8(a + 1);
    return { u8, u16, s16: (a) => w16(u16(a)), u32: (a) => ((u16(a) << 16) | u16(a + 2)) >>> 0 };
}
const A6 = 0x5bf00;
const BASE = 0x109be;
const v16 = (m, off) => m.s16(A6 + off);

// &047AA on the state at `top` with the camera matrix made at `lists`:
// each dot in view (and whether it is), and the pixels the ST plots.
function stDots(top, lists) {
    const missile = top.u8(A6 + 0x2c9) !== 0;
    const docked = top.u8(A6 + 0x2ca) !== 0;
    const iris = v16(lists, 0x27c);
    if (missile ? iris !== 0 : docked) return null;            // the dots weren't run
    const at = missile ? [0x26a, 0x26c, 0x26e] : [0x12e, 0x130, 0x132];
    const [px, py, pz] = at.map((o) => v16(top, o));
    const m = Array.from({ length: 9 }, (_, i) => v16(lists, 0x168 + 2 * i));
    const win = missile ? { ...MISSILE_VIEW, ymax: MISSILE_VIEW.ymax - iris } : VIEW;
    const dots = [];
    const pixels = new Set();
    for (let i = 0; i < 40; i++) {
        const x0 = v16(top, 0x80c + 4 * i),
            z0 = v16(top, 0x80e + 4 * i);
        const d1 = w16(x0 - px),
            d2 = w16(0 - py),
            d3 = w16(z0 - pz);
        // sub_04092: the matrix by columns, each term floored, words wrapping
        const x = w16(fmul(m[0], d1) + fmul(m[3], d2) + fmul(m[6], d3));
        const y = w16(fmul(m[1], d1) + fmul(m[4], d2) + fmul(m[7], d3));
        const z = w16(fmul(m[2], d1) + fmul(m[5], d2) + fmul(m[8], d3));
        const z2 = w16(2 * z),
            nz2 = w16(-z2);
        const seen = !(z <= 2 || x < nz2 || x > z2 || y < nz2 || y > z2);
        const dot = { i, x0, z0, x, y, z, seen };
        dots.push(dot);
        if (!seen) continue;
        const sx = w16(proj(x, z) + 143),
            sy = w16(proj(y, z) + 68);
        if (!(sx > win.xmin && sx < win.xmax && sy > win.ymin && sy < win.ymax)) continue;
        dot.sx = sx;
        dot.sy = sy;
        dot.plotted = true;
        const add = (a, b) => pixels.add(`${a},${b}`);
        add(sx, sy);
        if (z < 0x1000) add(sx, sy + 1);
        if (z < 0x700) {
            add(sx + 1, sy);
            add(sx + 1, sy + 1);
        }
    }
    return { dots, pixels, missile, win };
}

// The gunsight's pixels from STAR.PRG (D_0732A: words a row, rows, the
// hotspot, then each row's planes), relative to the sight.
function sightBitmap() {
    const prg = fs.readFileSync("build/st/STAR.PRG");
    const at = 28 + 0x0732a;
    const s16 = (o) => w16(prg.readUInt16BE(at + o));
    const [words, rows, hx, hy] = [0, 2, 4, 6].map(s16);
    const out = [];
    for (let r = 0; r < rows; r++)
        for (let g = 0; g < words / 4; g++) {
            const planes = [0, 1, 2, 3].map((k) => prg.readUInt16BE(at + 8 + 2 * (r * words + 4 * g + k)));
            for (let b = 0; b < 16; b++) if (planes.some((p) => (p >> (15 - b)) & 1)) out.push([16 * g + b - hx, r - hy]);
        }
    return out;
}

// &087FA: the bolt's lines for the count t and the target, cut.
function stBolt(t, tx, ty) {
    const out = [];
    for (const [ox, oy] of [
        [384, 150],
        [384, 170],
        [-64, 150],
        [-64, 170],
    ]) {
        let d6 = w16(tx - ox),
            d7 = w16(ty - oy);
        let x = w16(ox + (d6 & 3)),
            y = w16(oy + (d7 & 3));
        d6 >>= 2;
        d7 >>= 2;
        const k = 4 - t;
        const xf = w16(x + d6 * k),
            yf = w16(y + d7 * k);
        const line = clip2d([xf, yf, w16(xf - d6), w16(yf - d7)]);
        if (line) out.push(line);
    }
    return out;
}

// &07E6E: the gun's place on the screen for an object's record (camera
// space +28/+2A/+2C, type +0) and its gun height.
const GUN_Y = 0x0af12;
let gunY = null;
function gunStart(mem, rec) {
    if (!gunY) {
        const prg = fs.readFileSync("build/st/STAR.PRG");
        gunY = Array.from({ length: 30 }, (_, t) => w16(prg.readUInt16BE(28 + GUN_Y + 2 * t)));
    }
    const type = mem.u16(rec);
    const cx = mem.s16(rec + 0x28),
        cy = w16(mem.s16(rec + 0x2a) + (gunY[type] ?? 0)),
        cz = mem.s16(rec + 0x2c);
    if (cz === 0) return null;
    return [w16(proj(cx, cz) + 143), w16(proj(cy, cz) + 68)];
}
const RECORDS = A6 + 0x129a;
const recordOf = (s) => RECORDS + 64 * s;
const drawList = (mem) => {
    const n = mem.u16(A6 + 0x23e);
    const p = mem.u32(A6 + 0x94);
    return Array.from({ length: n }, (_, k) => mem.u32(p + 4 * k));
};

// random8 and random32 (&046B2, &04692), as the port's random.6502 has them.
function random8(st, d0) {
    const s = (d0 + st.mx) & 0xffff;
    const word = ((st.lag[0] << 8) | st.lag[1]) + s;
    st.lag[1] = word & 0xff;
    st.lag[0] = (word >> 8) & 0xff;
    let c = word >> 16;
    const round = () => {
        let a = st.lag[0] + st.lag[4] + c;
        const c1 = a >> 8;
        a = (a & 0xff) + st.lag[5] + c1;
        c = a >> 8;
        a &= 0xff;
        st.lag[0] = a;
        st.lag[5] = st.lag[4];
        st.lag[4] = st.lag[3];
        st.lag[3] = st.lag[2];
        st.lag[2] = st.lag[1];
        st.lag[1] = a;
        return a;
    };
    const hi = round();
    const lo = round();
    return (hi << 8) | lo;
}
function random32(st) {
    let r = st.r32;
    const out = r >>> 31;
    r = (r << 1) >>> 0;
    if (out || r === 0) r = (r ^ 0x1d872b41) >>> 0;
    r = ((r & 0xffff0000) | ((r + st.mx) & 0xffff)) >>> 0;
    const lag = ((st.lag[0] << 24) | (st.lag[1] << 16) | (st.lag[2] << 8) | st.lag[3]) >>> 0;
    st.r32 = (r + lag) >>> 0;
    return st.r32 >>> 16;
}
const rngState = (mem) => ({
    lag: Array.from({ length: 6 }, (_, i) => mem.u8(A6 + 0x5c + i)),
    r32: mem.u32(A6 + 0x64),
    mx: mem.u16(BASE + 0x01842),
});
const HANDLERS_FROM = 0x07a54,
    HANDLERS_TO = 0x08416;
const SHOT_CALL = 0x07ea2;

// ---------------------------------------------------------------------------
// --scenes: the shots' formula against the ST's own lines.
if (scenesPath) {
    const scenes = JSON.parse(fs.readFileSync(scenesPath, "utf8"));
    let lines = 0,
        matched = 0;
    for (let n = 0; n < scenes.frames.length; n++) {
        const fr = scenes.frames[n];
        const mem = stMemory(scenes.regions, fr.memory);
        const after = fr.drawn.filter((o) => o.object === "after").flatMap((o) => o.lines);
        for (const [x0, y0, x1, y1, colour] of after) {
            if (colour !== 1) continue;
            lines++;
            const found = y1 === 128 && drawList(mem).some((rec) => {
                const s = gunStart(mem, rec);
                const got = s && clip2d([s[0], s[1], x1, 128]);
                return got && got.join() === [x0, y0, x1, y1].join();
            });
            if (found) matched++;
            else if (lines - matched <= show) console.log(`  frame ${n}: [${x0}, ${y0}, ${x1}, ${y1}] is no drawn object's gun`);
        }
    }
    console.log(`viewrun --scenes: ${lines} shots' lines, ${matched} a drawn object's gun to the bottom edge`);
    process.exit(lines === matched ? 0 : 1);
}

// ---------------------------------------------------------------------------
// The machine, the spike and the map.
const sym = loadSymbols(path.join(build, "symbols.json"));
const need = (name) => {
    if (!(name in sym)) throw new Error(`no symbol ${name}`);
    return sym[name];
};
const map = JSON.parse(execFileSync("python3", ["-I", "tools/stmap.py", path.join(build, "symbols.json")], { encoding: "utf8" }));
const jsbeeb = path.resolve("node_modules/jsbeeb/src/test-machine.js");
const { TestMachine } = await import(pathToFileURL(jsbeeb).href);
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
load("SPIKE", need("spike_init"));
load("TABLES", where(need("TABLES")));
load("CODE2", where(need("CODE2")));
load("SHAPES", bank(need("BANK_SHAPES")));
load("WORLD", bank(need("BANK_WORLD")));
load("LOGIC", bank(need("BANK_LOGIC")));
load("WINDOW", bank(need("BANK_PIC")) + need("WIN_PIC") - 0x8000);
// the cockpit's screen (its window empty), and the picture's window rows
// as the screen holds them (tools/mkcockpit.py's --window)
const cockpit = fs.readFileSync("build/gen/cockpit.bin");
const winRaw = fs.readFileSync("build/gen/window.raw");

const STUB = 0x0140;
const STUB_DONE = STUB + 6;
// run: the routine at entry, from a stub with X set; the cycles from its
// start to each mark (addresses it reaches in turn), then to its end.
async function run(entry, x = 0, marks = []) {
    ram.set([0x78, 0xa2, x, 0x20, entry & 0xff, entry >> 8, 0x4c, STUB_DONE & 0xff, STUB_DONE >> 8], STUB);
    cpu.pc = STUB;
    cpu.s = 0xff;
    const t0 = tm.elapsedCycles;
    const times = [];
    for (const m of marks) {
        await tm.runUntilAddress(m, 5);
        if (cpu.pc !== m) throw new Error(`&${entry.toString(16)} didn't reach &${m.toString(16)}`);
        times.push(tm.elapsedCycles - t0);
    }
    await tm.runUntilAddress(STUB_DONE, 5);
    if (cpu.pc !== STUB_DONE) throw new Error(`&${entry.toString(16)} didn't return: pc &${cpu.pc.toString(16)}`);
    times.push(tm.elapsedCycles - t0);
    return times;
}
await run(need("spike_init"));

// Each variable and field the map holds, put from the ST's state (as
// tools/logicrun.mjs puts them).
function slotOf(ptr) {
    if (ptr === 0) return 0xff;
    if (ptr === 0x1218) return 140;
    if (ptr === 0x1258) return 141;
    const s = (ptr - (A6 + map.records.offset)) / map.records.size;
    if (!Number.isInteger(s) || s < 0 || s >= 140) throw new Error(`not a record: &${ptr.toString(16)}`);
    return s;
}
function stLong(steps, r, addr) {
    for (const [name, start, n] of steps.regions) if (addr >= start && addr + 4 <= start + n) return r[name].readUInt32BE(addr - start);
    throw new Error(`&${addr.toString(16)} isn't in the capture's regions`);
}
function putState(steps, r) {
    for (const v of map.variables) {
        const at = v.at;
        const st = r[v.region];
        if (v.kind === "byte") ram[at] = st[v.offset];
        else if (v.kind === "word") {
            ram[at] = st[v.offset + 1];
            ram[at + 1] = st[v.offset];
        } else if (v.kind === "word8") ram[at] = st[v.offset + 1];
        else if (v.kind === "long") for (let i = 0; i < 4; i++) ram[at + i] = st[v.offset + 3 - i];
        else if (v.kind === "raw") ram.set(st.subarray(v.offset, v.offset + v.count), at);
        else if (v.kind === "wlo" || v.kind === "whi" || v.kind === "barr") {
            const k = v.kind === "wlo" ? 1 : 0;
            for (let i = 0; i < v.count; i++) ram[at + i] = st[v.offset + i * v.stride + k];
        } else if (v.kind === "slots") for (let i = 0; i < v.count; i++) ram[at + i] = slotOf(st.readUInt32BE(v.offset + 4 * i));
        else if (v.kind === "index") {
            const e = (st.readUInt32BE(v.offset) - v.base) / v.stride;
            if (Number.isInteger(e) && e >= 0 && e <= 255) ram[at] = e;
        } else if (v.kind === "list") {
            const count = r[v.count_region].readUInt16BE(v.count_offset);
            const p = st.readUInt32BE(v.offset);
            ram[v.count_at] = count;
            for (let k = 0; k < count; k++) ram[at + count - 1 - k] = slotOf(stLong(steps, r, p + 4 * k));
        } else if (v.kind === "slotsdown") for (let i = 0; i < v.count; i++) ram[at + i] = slotOf(st.readUInt32BE(v.offset - 4 * (i + 1)));
        else if (v.kind === "slot") ram[at] = slotOf(st.readUInt32BE(v.offset));
        else throw new Error(`${v.name}: kind ${v.kind}`);
    }
    const rec = (s) =>
        s < 140
            ? r[map.records.region].subarray(map.records.offset + 64 * s, map.records.offset + 64 * s + 64)
            : r[map.records.silo.region].subarray(64 * (s - 140), 64 * (s - 140) + 64);
    for (const f of map.objects) {
        const [lo, hi] = f.at;
        for (let s = 0; s < f.slots; s++) {
            if (f.kind === "byte") ram[lo + s] = rec(s)[f.field];
            else if (f.kind === "word8") ram[lo + s] = rec(s)[f.field + 1];
            else if (f.kind === "word") {
                ram[lo + s] = rec(s)[f.field + 1];
                ram[hi + s] = rec(s)[f.field];
            }
        }
    }
}
const regionsAt = (frame, point) => {
    const p = frame.points[point];
    if (!p) return null;
    const out = {};
    for (const [name, hex] of Object.entries(p)) out[name] = Buffer.from(hex, "hex");
    return out;
};
const setD0 = (frame, point) => {
    const d0 = (frame.d0 ?? {})[point] ?? 0;
    ram[need("rng_d0")] = d0 & 0xff;
    ram[need("rng_d0") + 1] = d0 >> 8;
};
const callIn = (routine, bankName) => {
    ram[need("logic_bank")] = need(bankName) | need("ROMSEL_ANDY");
    ram[need("logic_call")] = need(routine) & 0xff;
    ram[need("logic_call") + 1] = need(routine) >> 8;
};

// The colours: the dots the ST's colour 2 in logical 1, the sight 15 in
// logical 2, so each is a bit plane of its own; the lines (logged, not read
// off the screen) logical 3.
const colourMap = need("colour_map");
for (let c = 0; c < 16; c++) ram[colourMap + c] = c === 2 ? 0x0f : c === 15 ? 0xf0 : 0xff;
const SCREEN = need("SCREEN");
const clearScreen = () => ram.fill(0, SCREEN, 0x8000);
// the logical colour's bit (1 or 2) at each pixel of the screen that has it
// (in the view, rows 10 to 128 and x 16 to 303, where its drawing is)
const at = (x, y) => (y >> 3) * 640 + (x >> 2) * 8 + (y & 7);
function screenPixels(bit) {
    const out = new Set();
    for (let y = VIEW.ymin; y <= VIEW.ymax; y++)
        for (let x = VIEW.xmin; x <= VIEW.xmax; x++) {
            const b = ram[SCREEN + at(x, y)];
            const p = x & 3;
            const c = (((b >> (7 - p)) & 1) << 1) | ((b >> (3 - p)) & 1);
            if (c & bit) out.add(`${x},${y}`);
        }
    return out;
}
// The screen as the ST's &06B7E leaves it in the missile view: the
// cockpit's, its window's rows 10 to 130 the picture's from 10 + m_iris on,
// cleared below 130 - m_iris; and when it's open, the bar's blocks ORed on
// (L_052EC: 17 - ((life - &F) asr 4 & &F) of them, 4 by 4, from x 209,
// each 6 left of the last and 2 more before the 9th and the 10th, in the
// ST's colour 7).
const PIX = [0x88, 0x44, 0x22, 0x11];
function stWindow(iris, life) {
    const s = Buffer.from(cockpit);
    for (let y = 10; y <= 130; y++)
        for (let x = VIEW.xmin; x <= VIEW.xmax; x += 4) {
            const r = y + iris;
            const cell = (x - VIEW.xmin) >> 2;
            s[at(x, y)] = r <= 130 ? winRaw[((r >> 3) - 1) * 576 + cell * 8 + (r & 7)] : 0;
        }
    if (iris === 0) {
        const blocks = 17 - ((w16(life - 0xf) >> 4) & 0xf);
        let x = 0xd3;
        for (let b = 0; b < blocks; b++) {
            for (let px = x - 2; px <= x + 1; px++)
                for (let y = 0x76; y < 0x76 + 4; y++) s[at(px, y)] |= PIX[px & 3] & ram[colourMap + 7];
            x -= 6;
            if (b + 1 === 8 || b + 1 === 9) x -= 2;
        }
    }
    return s;
}
const windowBad = (iris, life) => {
    const want = stWindow(iris, life);
    let bad = 0;
    for (let a = 0; a < want.length; a++) if (ram[SCREEN + a] !== want[a]) bad++;
    return bad;
};
// the screen with the open window on it, as the missile view leaves it
const cockpitPic = stWindow(0, 0x10f);
// the line log's entries since spike_over cleared it
function loggedLines(slot) {
    const n = ram[need("log_n")] | (ram[need("log_n") + 1] << 8);
    const log = bank(need("BANK_LOG")) + (need("line_log") - 0x8000);
    const out = [];
    for (let k = 0; k < n; k++) {
        const e = ram.subarray(log + 9 * k, log + 9 * k + 9);
        if (e[0] !== slot) continue;
        out.push([w16(e[2] | (e[3] << 8)), e[4], w16(e[5] | (e[6] << 8)), e[7]]);
    }
    return out;
}
const key = (l) => l.join(",");
const sameLines = (a, b) => a.map(key).sort().join(";") === b.map(key).sort().join(";");
// lines the same but for each end within a pixel
const nearLines = (a, b) => {
    if (a.length !== b.length) return false;
    const left = [...b];
    for (const l of a) {
        const i = left.findIndex((m) => l.every((v, k) => Math.abs(v - m[k]) <= 1) || [l[2], l[3], l[0], l[1]].every((v, k) => Math.abs(v - m[k]) <= 1));
        if (i < 0) return false;
        left.splice(i, 1);
    }
    return true;
};

const sight = sightBitmap();
const BOLT = need("VIEW_BOLT"),
    SHOT = need("VIEW_SHOT");
// spike_under's drawing, timed from its start to its end, and the dots
// from theirs
const marksUnder = [need("spike_under_draw"), need("dots_draw")];
const cyc = { under: [], dots: [], erase: [], bolt: [], shots: [], window: [], windowOpen: [] };
const tally = { frames: 0, mvFrames: 0, mvBad: 0, mvLeft: 0, dotFrames: 0, stDots: 0, exact: 0, near: 0, edge: 0, missed: 0, extra: 0, model: 0, pixWant: 0, pixExact: 0, pixNear: 0, pixEdge: 0, sight: 0, sightBad: 0, erased: 0, unerased: 0, bolts: 0, boltBad: 0, boltNear: 0, shots: 0, shotBad: 0, replayBad: 0 };
const bad = [];
const note = (s) => {
    if (bad.length < show * 6) bad.push(s);
};

for (const stepsPath of args) {
    const steps = JSON.parse(fs.readFileSync(stepsPath, "utf8"));
    const name = path.basename(path.dirname(stepsPath));
    for (let n = 0; n < steps.frames.length; n++) {
        const fr = steps.frames[n];
        const order = fr.order || [];
        const poked = (from, to) => order.slice(order.lastIndexOf(from) + 1, order.lastIndexOf(to)).includes("poke");
        const top = regionsAt(fr, "top"),
            lists = regionsAt(fr, "lists");
        // -- the gunsight and the dots, or the missile view's window (whose
        // frames have no lists point: render's state, as world_after leaves
        // what the drawing reads, stands in)
        const drawn = lists ? "lists" : "render";
        if (top && fr.points[drawn] && !poked("top", drawn)) {
            tally.frames++;
            const topMem = stMemory(steps.regions, fr.points.top);
            const listsMem = stMemory(steps.regions, fr.points[drawn]);
            const missile = topMem.u8(A6 + 0x2c9) !== 0;
            const under = async (fill) => {
                putState(steps, top);
                setD0(fr, "top");
                callIn("world_lists", "BANK_WORLD");
                fill();
                return run(need("spike_under"), 0, marksUnder);
            };
            const model = stDots(topMem, listsMem);
            let got, ignore = new Set();
            if (missile) {
                // the window and its bar, alone (the dots in colour 0),
                // drawn whole from the cockpit's screen, as the ST copies it
                tally.mvFrames++;
                ram[colourMap + 2] = 0;
                const iris = v16(listsMem, 0x27c);
                const life = v16(listsMem, 0x276);
                const fresh = () => {
                    ram.set(cockpit, SCREEN);
                    ram[need("win_shown")] = 0xff;
                };
                const t = await under(fresh);
                cyc.window.push(t[1] - t[0]);
                const bad = windowBad(iris, life);
                if (bad) {
                    tally.mvBad++;
                    note(`${name} frame ${n}: the missile view's window at m_iris ${iris}: ${bad} bytes not the ST's`);
                }
                const picture = screenPixels(1);
                if (iris === 0) {
                    // erased and drawn again, as the next frame on the
                    // screen is: what the erase took put back
                    await run(need("spike_erase"));
                    const t2 = await under(() => {});
                    cyc.windowOpen.push(t2[1] - t2[0]);
                    const bad2 = windowBad(iris, life);
                    if (bad2) {
                        tally.mvBad++;
                        note(`${name} frame ${n}: the open window put back: ${bad2} bytes not the ST's`);
                    }
                }
                // with the dots: those that change the picture's bit plane
                ram[colourMap + 2] = 0x0f;
                await under(fresh);
                got = new Set([...screenPixels(1)].filter((p) => !picture.has(p)));
                ignore = picture;
            } else {
                // after the missile view, its window shown still: cleared
                const after = ram[need("win_shown")] !== 0xff;
                const t = await under(() => ram.set(after ? cockpitPic : cockpit, SCREEN));
                if (after) tally.mvLeft++;
                else {
                    cyc.under.push(t[2] - t[0]);
                    cyc.dots.push(t[2] - t[1]);
                }
                got = screenPixels(1);
            }
            // the dots
            if (model) {
                tally.dotFrames++;
                for (const d of model.dots) {
                    const moved = listsMem.s16(A6 + 0x80c + 4 * d.i) !== d.x0 || listsMem.s16(A6 + 0x80e + 4 * d.i) !== d.z0;
                    if (d.seen === moved) {
                        tally.model++;
                        note(`${name} frame ${n}: dot ${d.i} ${d.seen ? "in view but moved" : "outside but kept"}`);
                    }
                }
                // each of the ST's dots, by its first pixel, drawn or within
                // a pixel of one drawn (two dots may share a pixel); each
                // pixel drawn one of the ST's, or within a pixel of one; but
                // not where the missile view's picture has the pixel already
                const want = new Set([...model.pixels].filter((p) => !ignore.has(p)));
                const near = (set, x, y) => [-1, 0, 1].some((dx) => [-1, 0, 1].some((dy) => set.has(`${x + dx},${y + dy}`)));
                // (a dot a pixel off can fall just outside the window, or
                // just inside it, its second column and row with it)
                const win = model.win;
                const edge = (x, y) => x <= win.xmin + 2 || x >= win.xmax - 1 || y <= win.ymin + 2 || y >= win.ymax - 1;
                for (const d of model.dots.filter((dd) => dd.plotted && !ignore.has(`${dd.sx},${dd.sy}`))) {
                    tally.stDots++;
                    if (got.has(`${d.sx},${d.sy}`)) tally.exact++;
                    else if (near(got, d.sx, d.sy)) tally.near++;
                    else if (edge(d.sx, d.sy) || near(ignore, d.sx, d.sy)) tally.edge++;
                    else {
                        tally.missed++;
                        note(`${name} frame ${n}: the ST's dot ${d.i} at (${d.sx}, ${d.sy}) z ${d.z} not drawn`);
                    }
                }
                for (const p of got) {
                    const [x, y] = p.split(",").map(Number);
                    if (want.has(p)) tally.pixExact++;
                    else if (near(model.pixels, x, y)) tally.pixNear++;
                    else if (edge(x, y)) tally.pixEdge++;
                    else {
                        tally.extra++;
                        note(`${name} frame ${n}: a dot's pixel at (${x}, ${y}) the ST doesn't plot`);
                    }
                }
                tally.pixWant += want.size;
            } else if (got.size) {
                tally.extra += got.size;
                note(`${name} frame ${n}: ${got.size} dots' pixels where the ST runs no dots`);
            }
            if (!missile) {
                // the sight
                const sx = topMem.s16(A6 + 0x244),
                    sy = topMem.s16(A6 + 0x246);
                const shown = sx >= 16 && sx < 303 && sy >= 10 && sy < 128;
                const wantSight = new Set(shown ? sight.map(([dx, dy]) => `${sx + dx},${sy + dy}`) : []);
                const gotSight = screenPixels(2);
                if (shown) tally.sight++;
                if ([...wantSight].sort().join() !== [...gotSight].sort().join()) {
                    tally.sightBad++;
                    note(`${name} frame ${n}: the sight at (${sx}, ${sy}): ${gotSight.size} pixels, the ST ${wantSight.size}`);
                }
                // erased, it's gone: the cockpit as it was
                const te = await run(need("spike_erase"));
                cyc.erase.push(te[0]);
                if (Buffer.from(ram.subarray(SCREEN, 0x8000)).equals(cockpit)) tally.erased++;
                else {
                    tally.unerased++;
                    note(`${name} frame ${n}: something left after the erase`);
                }
            }
        }
        // -- the bolt
        const render = regionsAt(fr, "render");
        if (lists && render && !poked("lists", "render")) {
            const listsMem = stMemory(steps.regions, fr.points.lists);
            const renderMem = stMemory(steps.regions, fr.points.render);
            putState(steps, lists);
            setD0(fr, "lists");
            callIn("world_after", "BANK_LOGIC");
            await run(need("spike_logic"));
            clearScreen();
            ram[need("shot_n")] = 0;                    // (the bolt alone: no shots left from before)
            const t = await run(need("spike_over"));
            const before = v16(listsMem, 0x284) & 0xffff,
                after = v16(renderMem, 0x284) & 0xffff;
            const drawn = !listsMem.u8(A6 + 0x2c9) && (before !== 0 || after !== 0);
            const want = drawn ? stBolt(after, v16(renderMem, 0x24c), v16(renderMem, 0x24e)) : [];
            const gotLines = loggedLines(BOLT);
            if (drawn) {
                tally.bolts++;
                cyc.bolt.push(t[0]);
            }
            if (!sameLines(gotLines, want)) {
                if (nearLines(gotLines, want)) tally.boltNear++;
                else {
                    tally.boltBad++;
                    note(`${name} frame ${n}: the bolt (count ${after}): port ${JSON.stringify(gotLines)} ST ${JSON.stringify(want)}`);
                }
            }
        }
        // -- the shots
        const flight = regionsAt(fr, "flight"),
            handlers = regionsAt(fr, "handlers");
        if (flight && handlers && !poked("flight", "handlers")) {
            const flightMem = stMemory(steps.regions, fr.points.flight);
            const handlersMem = stMemory(steps.regions, fr.points.handlers);
            // the ST's numbers, replayed from `flight` through the handlers' calls
            const rng = rngState(flightMem);
            const ends = [];
            for (const [routine, d0, caller] of fr.rng) {
                if (caller < HANDLERS_FROM || caller >= HANDLERS_TO) continue;
                if (routine === "random8") random8(rng, d0);
                else {
                    const r = random32(rng);
                    if (caller === SHOT_CALL) ends.push((r & 0x7f) + 0x60);
                }
            }
            const want = rngState(handlersMem);
            if (want.r32 !== rng.r32 || want.lag.join() !== rng.lag.join()) {
                tally.replayBad++;
                note(`${name} frame ${n}: the numbers' replay doesn't reach the ST's at handlers`);
            }
            putState(steps, flight);
            setD0(fr, "flight");
            ram[need("shot_n")] = 0;                    // (this step's shots alone: a frame draws them all since the last)
            callIn("object_handlers", "BANK_WORLD");
            await run(need("spike_logic"));
            clearScreen();
            ram[need("bolt_shown")] = 0;                // (the shots alone)
            const t = await run(need("spike_over"));
            const gotLines = loggedLines(SHOT);
            const drawnNow = drawList(flightMem);
            tally.shots += ends.length;
            if (ends.length) cyc.shots.push(t[0]);
            const kept = Math.min(ends.length, need("SHOTS"));
            let ok = gotLines.length <= kept;
            // each end the ST's, in order (the log holds them by record, from the last)
            const byEnd = [...gotLines].reverse();
            for (let k = 0; ok && k < byEnd.length; k++) {
                const l = byEnd[k];
                const end = l[3] === 128 ? l[2] : l[1] === 128 ? l[0] : null;
                if (end !== ends[k]) ok = false;
                const starts = drawnNow.map((rec) => gunStart(flightMem, rec)).filter(Boolean);
                if (!starts.some((s) => key(clip2d([s[0], s[1], ends[k], 128]) ?? []) === key(l))) ok = false;
            }
            if (gotLines.length !== kept) ok = false;
            if (!ok) {
                tally.shotBad++;
                note(`${name} frame ${n}: shots: port ${JSON.stringify(gotLines)}, the ST's ends ${JSON.stringify(ends)}`);
            }
        }
    }
}

const mean = (a) => (a.length ? Math.round(a.reduce((s, v) => s + v, 0) / a.length) : 0);
const most = (a) => (a.length ? Math.max(...a) : 0);
console.log(`viewrun: ${tally.frames} frames, ${tally.dotFrames} with dots`);
console.log(`  dots: the ST plots ${tally.stDots}: ${tally.exact} drawn exactly, ${tally.near} within a pixel, ${tally.edge} not drawn at the window's edge, ${tally.missed} not drawn; the model disagrees with the capture ${tally.model} times`);
console.log(`        the port's pixels: ${tally.pixExact} of the ST's ${tally.pixWant}, ${tally.pixNear} within a pixel of one, ${tally.pixEdge} at the window's edge, ${tally.extra} further`);
console.log(`  sight: shown in ${tally.sight}, ${tally.sightBad} frames' pixels not the ST's`);
console.log(`  erase: ${tally.erased} frames emptied, ${tally.unerased} not`);
console.log(`  bolt: drawn in ${tally.bolts} frames, ${tally.boltNear} within a pixel, ${tally.boltBad} wrong`);
console.log(`  shots: ${tally.shots} the ST's, ${tally.shotBad} frames wrong; the numbers' replay wrong ${tally.replayBad} times`);
console.log(`  missile view: ${tally.mvFrames} frames, ${tally.mvBad} windows not the ST's; ${tally.mvLeft} frames after it cleared`);
if (wantCycles) {
    console.log(`  cycles: the sight and the dots mean ${mean(cyc.under)}, most ${most(cyc.under)}; the dots alone mean ${mean(cyc.dots)}, most ${most(cyc.dots)}`);
    console.log(`          erasing them mean ${mean(cyc.erase)}, most ${most(cyc.erase)}; the bolt mean ${mean(cyc.bolt)}, most ${most(cyc.bolt)}; frames with shots mean ${mean(cyc.shots)}, most ${most(cyc.shots)}`);
    console.log(`          the missile view's window drawn whole mean ${mean(cyc.window)}, most ${most(cyc.window)}; open and put back mean ${mean(cyc.windowOpen)}, most ${most(cyc.windowOpen)}`);
}
for (const b of bad) console.log("  " + b);
const failed = tally.missed + tally.extra + tally.model + tally.sightBad + tally.unerased + tally.boltBad + tally.shotBad + tally.replayBad + tally.mvBad;
process.exit(failed ? 1 : 0);
