// beeb_linebench.mjs: time line and clear routines on jsbeeb's Master 128.
//
//   node tools/beeb_linebench.mjs WORKDIR [--jsbeeb DIR] [--only NAME]
//
// WORKDIR is where tools/beeb_linebench.sh built the routines (each binary
// has a .sym file of "name hexaddr" pairs beside it). jsbeeb defaults to
// ../jsbeeb beside this project.
//
// Each line is drawn on its own: the end points go into zero page, the CPU
// starts at the routine's `bench` stub (SEI, JSR routine, JMP-to-self) and runs
// until it reaches `bench_done`. The cycles are jsbeeb's own count, less the
// stub's, measured with a routine that is a bare RTS. Interrupts are off, so
// nothing else is counted. Every routine is also checked: drawn alone onto a
// clear screen, a line must light the pixels a line should (the right number,
// each within a pixel of the true segment), so a fast but wrong routine can't
// pass.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : dflt;
};
const work = args[0];
if (!work) {
    console.error("usage: node tools/beeb_linebench.mjs WORKDIR [--jsbeeb DIR] [--only NAME]");
    process.exit(2);
}
const jsbeebDir = path.resolve(opt("--jsbeeb", path.join(here, "..", "..", "jsbeeb")));
const only = opt("--only", null);
const { TestMachine } = await import(pathToFileURL(path.join(jsbeebDir, "src", "test-machine.js")).href);

// ---- deterministic line sets --------------------------------------------
function rng(seed) {
    let s = seed >>> 0;
    return () => {
        s ^= s << 13;
        s >>>= 0;
        s ^= s >>> 17;
        s ^= s << 5;
        s >>>= 0;
        return s / 4294967296;
    };
}
function lineSets(w, h) {
    const r = rng(1986);
    const ri = (n) => Math.floor(r() * n);
    const random = [];
    for (let i = 0; i < 400; i++) random.push([ri(w), ri(h), ri(w), ri(h)]);
    const short = [];
    while (short.length < 400) {
        const x0 = ri(w),
            y0 = ri(h);
        const len = 4 + r() * 36,
            a = r() * 2 * Math.PI;
        const x1 = Math.round(x0 + len * Math.cos(a)),
            y1 = Math.round(y0 + len * Math.sin(a));
        if (x1 >= 0 && x1 < w && y1 >= 0 && y1 < h) short.push([x0, y0, x1, y1]);
    }
    const n = Math.min(w, h) - 32; // a long line that fits either way
    const fixed = {
        point: [[100, 80, 100, 80]],
        horizontal: [[8, 80, 8 + n, 80]],
        vertical: [[100, 8, 100, 8 + Math.min(n, h - 16)]],
        diagonal: [[8, 8, 8 + Math.min(n, h - 16), 8 + Math.min(n, h - 16)]],
        "slope 1:2": [[8, 8, 8 + n, 8 + Math.floor(n / 2)]],
        "slope 1:4": [[8, 8, 8 + n, 8 + Math.floor(n / 4)]],
        "slope 2:1": [[8, 8, 8 + Math.floor((h - 16) / 2), h - 8]],
        "slope 4:1": [[8, 8, 8 + Math.floor((h - 16) / 4), h - 8]],
    };
    return { random, short, fixed };
}

// ---- targets ---------------------------------------------------------------
// Each target names a binary in WORKDIR (with a NAME.sym of its addresses, or a
// fixed load address), the routine's entry, where its end points go in zero
// page, any other bytes to poke first, and its screen's layout (for the check).
// `pixels(line)` is how many pixels the routine should light: Elite's, RTW's
// and Tricky's leave one end point unlit (measured: each lights
// max(|dx|,|dy|) pixels); NJ's lights both.
const closed = ([x0, y0, x1, y1]) => Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) + 1;
const open = ([x0, y0, x1, y1]) => Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0));

const m4Screen = { base: 0x6000, rowBytes: 256, bpp: 1, width: 256, height: 160 };
const lineTestZp = [0x70, 0x71, 0x72, 0x73]; // startx, starty, endx, endy

const targets = [
    { name: "Elite LOIN (cassette)", bin: "LINEM4", entry: "elite", zp: lineTestZp, screen: m4Screen, pixels: open },
    { name: "RTW", bin: "LINEM4", entry: "rtw", zp: lineTestZp, screen: m4Screen, pixels: open },
    { name: "Tricky", bin: "LINEM4", entry: "tricky", zp: lineTestZp, screen: m4Screen, pixels: open },
    { name: "NJ", bin: "LINEM4", entry: "nj", zp: lineTestZp, screen: m4Screen, pixels: closed },
    { name: "NJ + Hamiltonian 1:2", bin: "LINEM4H", entry: "nj", zp: lineTestZp, screen: m4Screen, pixels: closed },
    // Master Elite's LOIN, called in place in the game's own code (BCODE, as
    // Moxon's repository assembles it): 4 colours, 512-byte rows, screen in
    // shadow RAM at &4000, which LOIN reaches by setting ACCCON's X bit.
    // Addresses from that build's compile.txt; COL (&11) = &FF is colour 3.
    {
        name: "Elite LOIN (Master)",
        bin: "BCODE.unprot.bin",
        load: 0x1300,
        entry: 0x1728,
        zp: [0x4a, 0x4b, 0x4c, 0x4d],
        poke: [[0x11, 0xff]],
        screen: { base: 0x4000, rowBytes: 512, bpp: 2, width: 256, height: 160, shadow: true },
        pixels: open,
    },
];
if (fs.existsSync(path.join(work, "targets.json"))) {
    for (const t of JSON.parse(fs.readFileSync(path.join(work, "targets.json"), "utf8"))) {
        t.pixels = t.endpoint === "open" ? open : closed;
        targets.push(t);
    }
}

function readSyms(bin) {
    const sym = {};
    const f = path.join(work, bin + ".sym");
    if (!fs.existsSync(f)) return sym;
    const text = fs.readFileSync(f, "utf8");
    // beebasm prints "name&1234"; baron prints "name 1234".
    for (const m of text.matchAll(/([A-Za-z_][A-Za-z0-9_]*)\s*&?\s*([0-9A-Fa-f]{1,4})\b/g)) sym[m[1]] = parseInt(m[2], 16);
    return sym;
}

// ---- the machine -------------------------------------------------------------
const tm = new TestMachine("Master");
await tm.initialise();
const origLog = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = origLog;
const cpu = tm.processor;
const ram = cpu.ramRomOs; // jsbeeb's Master map: main RAM at 0, LYNNE at &B000 (shadow &3000 + &8000)
const boot = tm.snapshot();

// The stub: SEI / JSR entry / JMP-to-self, then a bare RTS to time it against.
const STUB = 0x0e00;
const BENCH_DONE = STUB + 4;
const NULL_RTS = STUB + 7;

function load(t, sym) {
    tm.restore(boot);
    const data = fs.readFileSync(path.join(work, t.bin));
    const at = t.load ?? sym.start;
    for (let i = 0; i < data.length; i++) ram[at + i] = data[i];
    const stub = [0x78, 0x20, 0, 0, 0x4c, BENCH_DONE & 0xff, BENCH_DONE >> 8, 0x60];
    stub.forEach((b, i) => (ram[STUB + i] = b));
}

async function call(entry) {
    ram[STUB + 2] = entry & 0xff;
    ram[STUB + 3] = entry >> 8;
    cpu.pc = STUB;
    cpu.s = 0xff;
    const before = tm.elapsedCycles;
    try {
        await tm.runUntilAddress(BENCH_DONE, 0.05);
    } catch {
        throw new Error(`no return within 0.05s; pc=&${cpu.pc.toString(16)}`);
    }
    return tm.elapsedCycles - before;
}

const screenIndex = (scr, addr) => (scr.shadow ? addr + 0x8000 : addr);
function clearScreen(scr) {
    const bytes = scr.rowBytes * Math.ceil(scr.height / 8);
    for (let i = 0; i < bytes; i++) ram[screenIndex(scr, scr.base + i)] = 0;
}
function setLine(t, sym, line) {
    t.zp.forEach((where, i) => (ram[typeof where === "number" ? where : sym[where]] = line[i]));
    for (const [addr, val] of t.poke ?? []) ram[addr] = val;
}

// Lit pixels, whatever their colour. MODE 1: a pixel's bits are b(7-p) and
// b(3-p). MODE 2: left pixel bits 7,5,3,1, right pixel 6,4,2,0.
function litPixels(scr) {
    const out = [];
    const ppb = 8 / scr.bpp;
    for (let y = 0; y < scr.height; y++) {
        for (let c = 0; c < scr.width / ppb; c++) {
            const b = ram[screenIndex(scr, scr.base + (y >> 3) * scr.rowBytes + c * 8 + (y & 7))];
            if (!b) continue;
            for (let p = 0; p < ppb; p++) {
                let m;
                if (scr.bpp === 1) m = 0x80 >> p;
                else if (scr.bpp === 2) m = (0x88 >> p) & 0xff;
                else m = p === 0 ? 0xaa : 0x55;
                if (b & m) out.push([c * ppb + p, y]);
            }
        }
    }
    return out;
}

function distToSegment([px, py], [x0, y0, x1, y1]) {
    const dx = x1 - x0,
        dy = y1 - y0;
    const L = dx * dx + dy * dy;
    let t = L ? ((px - x0) * dx + (py - y0) * dy) / L : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (x0 + t * dx), py - (y0 + t * dy));
}

function fit(points) {
    // least squares cycles = a + b * pixels
    const n = points.length;
    let sx = 0,
        sy = 0,
        sxx = 0,
        sxy = 0;
    for (const [x, y] of points) {
        sx += x;
        sy += y;
        sxx += x * x;
        sxy += x * y;
    }
    const b = (n * sxy - sx * sy) / (n * sxx - sx * sx);
    return { setup: (sy - b * sx) / n, perPixel: b };
}

const results = [];
for (const t of targets) {
    if (only && !t.name.toLowerCase().includes(only.toLowerCase())) continue;
    if (!fs.existsSync(path.join(work, t.bin))) {
        console.log(`skip ${t.name}: ${t.bin} not built`);
        continue;
    }
    const sym = readSyms(t.bin);
    load(t, sym);
    const entry = typeof t.entry === "number" ? t.entry : sym[t.entry];
    const stub = await call(NULL_RTS);
    const sets = lineSets(t.screen.width, t.screen.height);
    if (t.init) await call(sym[t.init]);

    // Check: each of the first 200 random and short lines alone on a clear screen.
    let bad = 0,
        maxDev = 0;
    const firstBad = [];
    for (const line of [...sets.random.slice(0, 200), ...sets.short.slice(0, 200), ...Object.values(sets.fixed).flat()]) {
        clearScreen(t.screen);
        setLine(t, sym, line);
        try {
            await call(entry);
        } catch (e) {
            // A hang may have run wild through memory: reload before going on.
            bad++;
            if (firstBad.length < 3) firstBad.push({ line, hang: e.message });
            load(t, sym);
            if (t.init) await call(sym[t.init]);
            continue;
        }
        const lit = litPixels(t.screen);
        const devs = lit.map((p) => distToSegment(p, line));
        maxDev = Math.max(maxDev, ...devs, 0);
        const far = devs.filter((d) => d > 1.0);
        if (lit.length !== t.pixels(line) || far.length) {
            bad++;
            if (firstBad.length < 3) firstBad.push({ line, lit: lit.length, want: t.pixels(line), far: far.length });
        }
    }

    const row = { name: t.name, stub, bad, maxDev, firstBad, sets: {} };
    console.log(`${t.name}: stub (SEI, JSR, RTS) ${stub} cycles`);
    for (const [setName, lines] of [
        ["random", sets.random],
        ["short", sets.short],
        ...Object.entries(sets.fixed),
    ]) {
        clearScreen(t.screen);
        let cyc = 0,
            pix = 0;
        const pts = [];
        let hung = false;
        for (const line of lines) {
            setLine(t, sym, line);
            let c;
            try {
                c = (await call(entry)) - stub;
            } catch {
                hung = true;
                load(t, sym);
                if (t.init) await call(sym[t.init]);
                break;
            }
            const p = t.pixels(line);
            cyc += c;
            pix += p;
            pts.push([p, c]);
        }
        const r = hung
            ? { hung: true, perPixel: NaN, perLine: NaN }
            : { lines: lines.length, cycles: cyc, pixels: pix, perPixel: cyc / pix, perLine: cyc / lines.length };
        if (!hung && lines.length > 2) Object.assign(r, { fit: fit(pts) });
        row.sets[setName] = r;
    }
    results.push(row);
    const s = row.sets;
    console.log(
        `${t.name.padEnd(26)} check ${bad ? bad + " BAD" : "ok"} (max ${maxDev.toFixed(2)} px off)  ` +
            `random ${s.random.perPixel.toFixed(1)} c/px (fit ${s.random.fit.setup.toFixed(0)} + ${s.random.fit.perPixel.toFixed(1)}/px)  ` +
            `short ${s.short.perPixel.toFixed(1)} c/px, ${s.short.perLine.toFixed(0)} c/line  ` +
            `point ${s.point.perLine.toFixed(0)} c  ` +
            Object.keys(sets.fixed)
                .filter((k) => k !== "point")
                .map((k) => `${k} ${s[k].perPixel.toFixed(1)}`)
                .join("  "),
    );
    if (bad) console.log("   first failures:", JSON.stringify(firstBad));
}
fs.writeFileSync(path.join(work, "linebench.json"), JSON.stringify(results, null, 2));
console.log(`wrote ${path.join(work, "linebench.json")}`);
