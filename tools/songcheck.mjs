// The title song (decision 5) on the disc, on jsbeeb's Master, against the
// Spectrum 128K's: the disc booted to its title, the song played for a
// pass and LOOP ticks into the next, as it goes round (tools/songmodel.py's
// model of tools/mksong.py's zx_bass conversion of build/zx/song.json):
//
// 1. After each tick (song.6502's song_work), the player's copy of the AY's
//    registers 0-13, and whether register 13 was written, must be the
//    Spectrum's after the same tick (the capture's writes, the pass's again
//    past its end).
// 2. The SN76489 as the disc wrote it, after each tick: each channel with no
//    bass its period and attenuation, the noise's control and attenuation,
//    and how often the tick wrote the control, as the model's; a channel
//    playing bass at period 1, its half-cycle and level the model's.
// 3. The bass's edges (song_irq.6502), each channel's: its volume between
//    its level and silence, a half-cycle on from the last edge's moment on
//    average (an edge is as late as its interrupt, but the next is timed
//    from when it was due), none further out than LATE, the first a
//    half-cycle from its tick's moment; as many in the pass as the model's.
// 4. The tick's rate (System VIA T1, free-running), each tick a
//    SONG_TICK_US on from the last.
// 5. With the end screen's bands taking channel A's timer (song_bands),
//    BANDS ticks from the song's start: channel A's low notes an octave up,
//    as the model's bands record has them, the rest as before.
// 6. The envelope's level, every shape at every step the model gives,
//    which the tune itself reaches few of.
//
// It writes the pass as the chip took it, build/tune/disc.json (tools/
// songwav.mjs's input: the Makefile's tune renders it and compares it
// with the model's zx_bass_chip.wav, tools/songcompare.py), and says what
// the song costs on the title: the CPU its interrupts take, by kind, and
// how long they and the key scan hold interrupts off.
//
//   node tools/songcheck.mjs
//
// Exits non-zero on a difference.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const jsbeeb = (f) => pathToFileURL(path.join(root, "node_modules/jsbeeb/src", f)).href;
const { TestMachine } = await import(jsbeeb("test-machine.js"));
const { SoundChip } = await import(jsbeeb("soundchip.js"));
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc, fieldCycles } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const model = JSON.parse(fs.readFileSync(path.join(root, "build/tune/model.json"), "utf8"));
const OUT = path.join(root, "build/tune");

const HZ = 2e6;
const US = 2;                           // cycles a microsecond
// An edge from its due moment, in microseconds: on its line at the median
// (no drift), and at the latest as late as the interrupts it waits behind
// (another channel's edge at the same moment, the vertical sync's, the key
// scan's interrupts off), which the 99th percentile bounds too.
const MEDIAN = 2;
const LATE_99 = 200;
const LATE = 400;
const EDGES = 0.002;                    // the pass's edges' furthest from the model's count, a fraction
const F = Object.fromEntries(model.fields.map((f, i) => [f, i]).filter(([f]) => f !== "ay"));

let bad = 0;
const fail = (what) => {
    bad++;
    if (bad <= 30) console.log(`songcheck: ${what}`);
};

// The chip, every byte it takes, timed.
class Recorder extends SoundChip {
    constructor() {
        super(() => {});
        this.writes = [];
    }
    advance() {}
    poke(value) {
        this.writes.push([this.scheduler.epoch, value]);
        super.poke(value);
    }
}

async function boot() {
    const chip = new Recorder();
    const tm = new TestMachine("Master", { soundChip: chip });
    await tm.initialise();
    const q = console.log;
    console.log = () => {};
    await tm.runUntilInput();
    console.log = q;
    loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
    return { tm, chip, cpu: tm.processor, ram: tm.processor.ramRomOs };
}

// The SN's registers as its bytes set them.
function snState() {
    const s = { tone: [0, 0, 0], att: [15, 15, 15, 15], noise: -1, latched: 0 };
    s.take = (v) => {
        if (v & 0x80) s.latched = (v >> 4) & 7;
        const r = s.latched, c = r >> 1;
        if (r & 1) s.att[c] = v & 15;
        else if (c === 3) s.noise = 0xe0 | (v & 7);
        else s.tone[c] = v & 0x80 ? (s.tone[c] & ~15) | (v & 15) : (s.tone[c] & 15) | ((v & 0x3f) << 4);
    };
    return s;
}

// Play the song from its start for `ticks` ticks, recording each tick's
// state; bands: song_bands called just after the start.
async function play(ticks, { bands = false, cost = false } = {}) {
    const m = await boot();
    const { tm, chip, cpu, ram } = m;
    const now = () => cpu.cycleSeconds * HZ + cpu.currentCycles;
    const recs = [], tickAt = [], edges = [[], [], []];
    let started = null, tickStart = -1, noiseW = 0, written = 0;
    const sn = snState();
    const T1 = () => (cpu.sysvia.t1c + 1) >>> 1;          // its count, in microseconds
    const word = (lo, hi, c) => ram[lo + c] | (ram[hi + c] << 8);
    // costs: each interrupt's cycles, less those nested in it, by what it did
    const intStack = [];
    const spent = { tick: 0, edge: 0 }, count = { tick: 0, edge: 0 };
    let held = { tick: 0, edge: 0, scan: 0 }, scanAt = null, offAt = null, longestOff = 0;
    const brk = cpu.brk;
    cpu.brk = function (isIrq) {
        if (isIrq && cost) intStack.push({ at: now(), nested: 0, kind: null, s: this.s });
        return brk.call(this, isIrq);
    };
    const hook = cpu.debugInstruction.add((pc, op) => {
        // (until SONG is read, the start's code lies where its code goes)
        if (started === null) {
            if (pc === sym.song_start && (cpu.romsel & 15) === sym.BANK_PIC) started = now();
            return false;
        }
        if (pc === sym["song_irq.tick"]) {
            // the tick's moment: T1 counts down from its latch since it
            tickAt.push(now() - US * (sym.SONG_TICK_US - 2 - T1()));
            if (intStack.length) intStack[intStack.length - 1].kind = "tick";
        } else if (pc === sym["song_irq.edge"] && intStack.length) intStack[intStack.length - 1].kind = "edge";
        else if (pc === sym["song_irq.edge_write"]) {
            // the edge's moment, its byte, the half-cycle its re-arm took
            const c = cpu.x;
            edges[c].push([now(), ram[sym.bass_phase + c], word(sym.bass_half_lo, sym.bass_half_hi, c)]);
        } else if (pc === sym["channel_bass.read"]) {
            // a bass begun: its first edge is due a half-cycle from the tick's moment
            const c = cpu.x;
            edges[c].push([null, tickAt[tickAt.length - 1], word(sym.bass_half_lo, sym.bass_half_hi, c)]);
        }
        else if (pc === sym.song_work) {
            tickStart = chip.writes.length;
            if (bands && recs.length === 0 && !ram[sym.sg_bands]) {
                // (song_bands, as end_on calls it, before the first tick's work)
                ram[sym.sg_bands] = 0xff;
            }
        } else if (pc === sym["song_work.worked"]) {
            for (; written < chip.writes.length; written++) sn.take(chip.writes[written][1]);
            noiseW = 0;
            for (let i = tickStart; i < chip.writes.length; i++) if ((chip.writes[i][1] & 0xf0) === 0xe0) noiseW++;
            const half = [0, 1, 2].map((c) => word(sym.bass_half_lo, sym.bass_half_hi, c));
            recs.push({
                ay: [...ram.slice(sym.sg_ay, sym.sg_ay + 14)], env: ram[sym.sg_restart] ? 1 : 0,
                tone: sn.tone.slice(), att: sn.att.slice(), noise: sn.noise, noise_w: noiseW, half,
                held: [0, 1, 2].map((c) => (half[c] ? ram[sym.bass_lvl + c] & 15 : -1)),
            });
        }
        if (cost) {
            // interrupts held off: the longest stretch with I set, and the
            // longest of those the key scan began
            if (cpu.p.i) {
                if (offAt === null) {
                    offAt = now();
                    scanAt = pc >= sym.fe_scan && pc < sym["fe_scan.scanned"] + 16;
                }
            } else if (offAt !== null) {
                const d = now() - offAt;
                if (d > longestOff) longestOff = d;
                if (scanAt) held.scan = Math.max(held.scan, d);
                offAt = null;
            }
            if (op === 0x40 && intStack.length && cpu.s === intStack[intStack.length - 1].s - 3) {
                const e = intStack.pop();
                const d = now() - e.at;
                if (intStack.length) intStack[intStack.length - 1].nested += d;
                if (e.kind) {
                    spent[e.kind] += d - e.nested;
                    count[e.kind]++;
                    held[e.kind] = Math.max(held[e.kind], e.kind === "tick" ? 0 : d - e.nested);
                }
            }
        }
        return false;
    });
    while (recs.length < ticks) {
        await tm.runFor(HZ / 10);
        if (started === null && tm.elapsedCycles > 60 * HZ) throw new Error("the song never started");
    }
    hook.remove();
    cpu.brk = brk;
    return { m, recs, tickAt, edges, started, spent, count, held, longestOff, chip };
}

// --- 1, 2: the whole pass and into the loop ---
const ticks = model.records.length;
const run = await play(ticks, { cost: true });
const { recs, tickAt, edges } = run;
let ayBad = 0, snBad = 0, firstAy = -1, firstSn = -1;
const show = (r) => JSON.stringify(r);
for (let k = 0; k < ticks; k++) {
    const want = model.records[k], got = recs[k];
    const ayDiff = want.slice(0, 14).some((v, i) => v !== got.ay[i]) || want[F.env] !== got.env;
    if (ayDiff) {
        ayBad++;
        if (firstAy < 0) {
            firstAy = k;
            fail(`tick ${k}: the AY's registers ${got.ay.join(",")} (13 written ${got.env}), the Spectrum's ` +
                `${want.slice(0, 14).join(",")} (${want[F.env]})`);
        }
    }
    const diffs = [];
    for (let c = 0; c < 3; c++) {
        const half = want[F.half0 + c];
        if (!half) {
            if (got.half[c]) diffs.push(`channel ${c} plays bass at ${got.half[c]}us`);
            if (got.tone[c] !== want[F.tone0 + c]) diffs.push(`channel ${c}'s period ${got.tone[c]}, not ${want[F.tone0 + c]}`);
            if (got.att[c] !== want[F.att0 + c]) diffs.push(`channel ${c}'s attenuation ${got.att[c]}, not ${want[F.att0 + c]}`);
        } else {
            if (got.tone[c] !== 1) diffs.push(`channel ${c}'s period ${got.tone[c]}, not the bass's 1`);
            if (got.half[c] !== half) diffs.push(`channel ${c}'s half-cycle ${got.half[c]}us, not ${half}`);
            if (got.held[c] !== want[F.held0 + c]) diffs.push(`channel ${c}'s bass level ${got.held[c]}, not ${want[F.held0 + c]}`);
        }
    }
    if (got.att[3] !== want[F.att3]) diffs.push(`the noise's attenuation ${got.att[3]}, not ${want[F.att3]}`);
    if (want[F.noise] >= 0 && got.noise !== (0xe0 | want[F.noise])) diffs.push(`the noise's control &${got.noise.toString(16)}, not ${want[F.noise]}`);
    if (got.noise_w !== want[F.noise_w]) diffs.push(`the noise's control written ${got.noise_w} times, not ${want[F.noise_w]}`);
    if (diffs.length) {
        snBad++;
        if (firstSn < 0) {
            firstSn = k;
            fail(`tick ${k}: ${diffs.join("; ")}\n  the disc's ${show(got)}\n  the model's ${show(want)}`);
        }
    }
}
const passes = `${model.length} ticks and ${ticks - model.length} more`;
if (!ayBad) console.log(`songcheck: the AY's registers after every tick, ${passes}: the Spectrum's`);
else fail(`the AY's registers differ after ${ayBad} of ${ticks} ticks`);
if (!snBad) console.log(`songcheck: the SN's registers and the bass after every tick: the model's`);
else fail(`the SN's registers differ after ${snBad} of ${ticks} ticks`);

// --- 3: the edges: each channel's runs, a bass begun to its end, each edge
// a half-cycle (the one its re-arm took) from the last, the first from its
// tick's moment ---
const TICK = sym.SONG_TICK_US;
const passEnd = tickAt[model.length];
let edgeCount = 0, extra = 0, worstLate = 0, worstFirst = 0, sumFirst = 0, firsts = 0, runs = 0;
const lateness = [];
for (const c of [0, 2]) {
    let alternate = true;
    let run = null;                     // the tick it began at, its half-cycle then, its edges' moments and halves
    const close = () => {
        if (!run || !run.t.length) return;
        runs++;
        // the run's line: the first edge due a half-cycle from its tick, each
        // after it a half-cycle after the last was
        let due = run.tick + US * run.h0;
        for (let i = 0; i < run.t.length; i++) {
            if (i) due += US * run.h[i - 1];
            const late = (run.t[i] - due) / US;
            lateness.push(late);
            worstLate = Math.max(worstLate, Math.abs(late));
        }
    };
    // the ticks the bass stopped at: an edge after one, before the tick's
    // work stopped it, is one the model hasn't
    const stops = [];
    for (let k = 1; k < recs.length; k++) if (recs[k - 1].half[c] && !recs[k].half[c]) stops.push(tickAt[k]);
    let s = 0;
    for (const [t, v, h] of edges[c]) {
        if (t === null) {
            // a bass begun at the tick v
            close();
            run = { tick: v, h0: h, t: [], h: [] };
            continue;
        }
        while (s < stops.length && stops[s] < run.tick) s++;
        if (s < stops.length && t > stops[s]) {
            if (t < passEnd) extra++;
            continue;
        }
        if (!run) continue;
        // (v: the phase the edge leaves, heard 0 or silent 15, from heard)
        if (run.t.length === 0) {
            const d = (t - run.tick) / US - run.h0;
            sumFirst += d;
            firsts++;
            worstFirst = Math.max(worstFirst, Math.abs(d));
            if (v !== 15) alternate = false;
        } else if ((v ^ run.v) !== 15) alternate = false;
        run.v = v;
        run.t.push(t);
        run.h.push(h);
        if (t < passEnd) edgeCount++;
    }
    close();
    if (!alternate) fail(`channel ${c}'s edges don't switch between its level and silence`);
}
lateness.sort((a, b) => a - b);
const pct = (p) => lateness[Math.min(lateness.length - 1, Math.floor(p * lateness.length))];
console.log(`songcheck: the bass's edges, ${runs} runs: ${edgeCount} in the pass (the model's ${model.edges}), and ${extra} ` +
    `between a run's last tick and its stop in the tick's work; each from its due moment ${pct(0.5).toFixed(1)}us late at ` +
    `the median, ${pct(0.99).toFixed(1)} at the 99th percentile, at most ${worstLate.toFixed(1)}us; a run's first ` +
    `${(sumFirst / firsts).toFixed(1)}us from a half-cycle after its tick on average, at most ${worstFirst.toFixed(1)}us`);
if (Math.abs(edgeCount - model.edges) > EDGES * model.edges) fail(`${edgeCount} edges in the pass, the model's ${model.edges}`);
if (Math.abs(pct(0.5)) > MEDIAN) fail(`the edges ${pct(0.5)}us from their line at the median`);
if (pct(0.99) > LATE_99) fail(`the edges ${pct(0.99)}us late at the 99th percentile`);
if (worstLate > LATE) fail(`an edge ${worstLate.toFixed(1)}us late`);

// --- 4: the tick ---
let worstTick = 0;
for (let k = 1; k < tickAt.length; k++) worstTick = Math.max(worstTick, Math.abs((tickAt[k] - tickAt[k - 1]) / US - TICK));
const rate = (tickAt.length - 1) / ((tickAt[tickAt.length - 1] - tickAt[0]) / HZ);
console.log(`songcheck: ${tickAt.length} ticks at ${rate.toFixed(3)} Hz, each ${TICK}us from the last within ${worstTick.toFixed(1)}us`);
if (worstTick > 2) fail(`a tick ${worstTick}us off ${TICK}us from the last`);     // (T1's count read to a microsecond)

// the costs, on the title, a field's
const FIELD = fieldCycles(sym);
const fields = (tickAt[tickAt.length - 1] - tickAt[0]) / FIELD;
const per = (k) => (run.spent[k] / fields).toFixed(0);
console.log(`songcheck: on the title, the tick's interrupts ${per("tick")} cycles a field (${(run.spent.tick / run.count.tick).toFixed(0)} a tick), ` +
    `the bass's ${per("edge")} (${(run.spent.edge / Math.max(1, run.count.edge)).toFixed(0)} an edge, ${(run.count.edge / fields).toFixed(2)} a field): ` +
    `${(100 * (run.spent.tick + run.spent.edge) / (fields * FIELD)).toFixed(1)}% of the CPU; an edge's interrupt ${(run.held.edge / US).toFixed(1)}us at most; ` +
    `interrupts off at most ${(run.longestOff / US).toFixed(1)}us at a time, the key scan's ${(run.held.scan / US).toFixed(1)}us`);

// the pass as the chip took it, from the first tick's moment, for songwav.mjs
const t0 = tickAt[0], tEnd = tickAt[model.length];
const disc = run.chip.writes.filter(([t]) => t >= run.started - 2 * HZ && t < tEnd).map(([t, v]) => [Math.max(0, Math.round(t - t0)), v]);
fs.mkdirSync(OUT, { recursive: true });
fs.writeFileSync(path.join(OUT, "disc.json"), JSON.stringify({ chip: "sn", hz: HZ, end: Math.round(tEnd - t0), writes: disc }) + "\n");
console.log(`songcheck: the pass as the chip took it -> ${path.relative(root, path.join(OUT, "disc.json"))}`);

// --- 5: the end screen's bands ---
const bandRun = await play(model.bands.length, { bands: true });
let bandBad = 0, lowA = 0;
for (let k = 0; k < model.bands.length; k++) {
    const want = model.bands[k], got = bandRun.recs[k];
    if (want[F.half0] === 0 && want[F.tone0] !== model.records[k][F.tone0]) lowA++;
    const ok = got.half[0] === 0 && got.tone[0] === want[F.tone0] && got.att[0] === want[F.att0] &&
        (want[F.half2] ? got.half[2] === want[F.half2] && got.tone[2] === 1 : got.tone[2] === want[F.tone2] && got.att[2] === want[F.att2]);
    if (!ok) {
        if (!bandBad) fail(`with the bands, tick ${k}: the disc's ${show(got)}\n  the model's ${show(want)}`);
        bandBad++;
    }
}
if (bandBad) fail(`with the bands, ${bandBad} of ${model.bands.length} ticks differ`);
else console.log(`songcheck: with the end screen's bands, ${model.bands.length} ticks: channel A's low notes ` +
    `(${lowA} ticks of them) an octave up, as the model's`);
if (!lowA) fail("the bands' ticks have none of channel A's low notes to check");

// --- 6: the envelope's level, every shape at every step the model gives,
// most of which the tune never reaches: from a stub, interrupts off, with
// the front end waiting for a field ---
{
    const { tm, cpu, ram } = bandRun.m;
    await tm.runUntilAddress(sym["fe_field.wait"], 5, { bank: sym.BANK_PIC });
    const IDLE = 0x0140, STUB = 0x0143;
    ram.set([0x4c, IDLE & 0xff, IDLE >> 8], IDLE);
    const call = async (routine) => {
        ram.set([0x20, routine & 0xff, routine >> 8, 0x4c, IDLE & 0xff, IDLE >> 8], STUB);
        cpu.p.i = true;
        cpu.pc = STUB;
        await tm.runUntilAddress(IDLE, 1);
    };
    let envBad = 0, steps = 0;
    for (let s = 0; s < 16; s++) {
        const want = model.envelope[s];
        ram[sym.sg_ay + 13] = s;
        ram[sym.sg_restart] = 0xff;
        await call(sym.envelope);
        for (let q = 0; q < want.length; q++) {
            if (q) {
                ram[sym.sg_env_q] = q & 0xff;
                ram[sym.sg_env_q + 1] = q >> 8;
                ram[sym.sg_env_held] = 0;
                await call(sym["envelope.level"]);
            }
            steps++;
            if (ram[sym.sg_env_level] !== want[q]) {
                if (!envBad) fail(`the envelope's shape ${s} at step ${q}: level ${ram[sym.sg_env_level]}, the model's ${want[q]}`);
                envBad++;
            }
        }
    }
    if (envBad) fail(`the envelope's level differs at ${envBad} of ${steps} shapes and steps`);
    else console.log(`songcheck: the envelope's level, ${steps} shapes and steps: the model's`);
}
process.exit(bad ? 1 : 0);
