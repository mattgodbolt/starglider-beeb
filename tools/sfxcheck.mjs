// The sound effects (decision 5) on the disc, on jsbeeb's Master, against
// the ST's: each capture's plays (tools/st_sfx.py: the YM2149's writes in
// Hatari, every effect from the game's own tester, and the meetings the
// game can make) played into the port's sfx_start at the same moments,
// and the SN76489's writes compared with the ST's converted as the port
// converts them (tools/mksfx.py): tone A's period on tone 0, its level
// at full (the tone's attenuation) or off; the noise's period on tone 2,
// its level the envelope's on the three channels or the two that are up.
// Each register's changes must match the ST's in value and order (a sweep
// that takes k of the ST's ticks a tick, every k-th of its periods), and
// in time, within SLACK: a start's at once; a Timer A effect's ticks once
// the ST's are moved to put its first a tick after its start, as the
// port's is (the ST's comes when Timer A's counter, left running from its
// last use, next reaches 0), and a sweep's end up to the k - 1 ticks later
// it comes; the envelope's steps within a field and a hundredth. The
// levels are compared from just after a window's first start, and the
// windows from an effect the port leaves out (nothing starts one) to the
// next not at all. Then the gates: nothing with the sound off, nothing
// while a sample plays (sound_field's count of it at its rate), a
// sample's start stopping an effect, and the sweeps that take more than
// one of the ST's ticks losing none of their own with a key held, whose
// scan is the vertical sync's longest work.
//
//   node tools/sfxcheck.mjs [--show] [CAPTURE.json ...]   (build/sfx/*/sfx.json)
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const jsbeeb = (f) => pathToFileURL(path.join(root, "node_modules/jsbeeb/src", f)).href;
const { TestMachine } = await import(jsbeeb("test-machine.js"));
const { SoundChip } = await import(jsbeeb("soundchip.js"));
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const gen = JSON.parse(fs.readFileSync(path.join(root, "build/gen/sfx.json"), "utf8"));
const HZ = 2e6;
const SLACK = 1e-3;                     // the port's start, and its interrupt's latency

const args = process.argv.slice(2);
const show = args.includes("--show");
let captures = args.filter((a) => !a.startsWith("--"));
if (!captures.length) {
    const dir = path.join(root, "build/sfx");
    captures = fs.existsSync(dir)
        ? fs.readdirSync(dir).map((d) => path.join(dir, d, "sfx.json")).filter((f) => fs.existsSync(f))
        : [];
}
if (!captures.length) {
    console.log("sfxcheck: no capture in build/sfx: tools/st_sfx.py run tests/st/sfx_all.txt build/sfx/all");
    process.exit(1);
}

let bad = 0;
const fail = (what) => {
    bad++;
    if (bad <= 20) console.log(`sfxcheck: ${what}`);
};

// The chip, its writes timed in CPU cycles, rendering nothing.
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

// The disc from engine_run's entry, its foreground idle at IDLE, with
// STUB to call a routine from (LDA #a : LDX #x : JSR r : JMP IDLE).
const IDLE = 0x0140, STUB = 0x0143;
async function machine() {
    const chip = new Recorder();
    const tm = new TestMachine("Master", { soundChip: chip });
    await tm.initialise();
    const q = console.log;
    console.log = () => {};
    await tm.runUntilInput();
    console.log = q;
    loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
    await tm.runUntilAddress(sym.engine_run, 60);
    const cpu = tm.processor;
    const ram = cpu.ramRomOs;
    ram.set([0x4c, IDLE & 0xff, IDLE >> 8], IDLE);
    cpu.pc = IDLE;
    const now = () => cpu.scheduler.epoch;
    const call = async (routine, a = 0, x = 0) => {
        await tm.runUntilAddress(IDLE, 1);
        ram.set([0xa9, a, 0xa2, x, 0x20, routine & 0xff, routine >> 8, 0x4c, IDLE & 0xff, IDLE >> 8], STUB);
        cpu.pc = STUB;
        const t = now();
        await tm.runUntilAddress(IDLE, 1);
        return t;
    };
    const runTo = async (cycle) => {
        const left = cycle - now();
        if (left > 0) await tm.runFor(left);
    };
    return { tm, cpu, ram, chip, now, call, runTo };
}

// The port's writes as each register's values, in seconds from `from`.
function snEvents(writes, from) {
    const ev = { t0p: [], t0a: [], t1a: [], t2p: [], t2a: [], nctl: [], na: [] };
    const reg = [0, 0, 0, 0];
    let latched = 0;
    for (const [c, v] of writes) {
        const t = (c - from) / HZ;
        if (v & 0x80) latched = v & 0x70;
        const ch = (latched >> 5) & 3;
        if (latched & 0x10) ev[["t0a", "t1a", "t2a", "na"][ch]].push([t, v & 15]);
        else if (ch === 3) ev.nctl.push([t, v & 7]);
        else {
            reg[ch] = v & 0x80 ? (reg[ch] & ~15) | (v & 15) : (reg[ch] & 15) | ((v & 0x3f) << 4);
            if (ch === 0) ev.t0p.push([t, reg[0]]);
            if (ch === 2) ev.t2p.push([t, reg[2]]);
        }
    }
    return ev;
}

const effect = (n) => gen.effects[n];
const stTick = (n) => (effect(n).rate ? 1 / effect(n).rate : 0);
const START = 1e-3;                     // a play's own writes come within this of it
// The Timer A handlers' code (the ST's &00228, &005AC, &006A4, and the
// unported &007C2 to &00A9D): a write from there is a tick's.
const TICKS = [[0x00228, 0x002c8], [0x005ac, 0x00626], [0x006a4, 0x0071e], [0x007c2, 0x00a9e]];
const ticking = (pc) => TICKS.some(([a, b]) => pc >= a && pc < b);

// The ST's writes, the whole capture, as the SN's registers would have
// them: each change of tone 0's level and the noise's from the start (both
// off), tone A's periods (every k-th of a sweep's ticks), the noise's
// clock, each tagged with what made it: a play's start, its timer's tick
// (the play), or its envelope's step (shapes 0-3 and 9: falling from 31,
// held at 0); and each timer play's first tick.
function stTimeline(capture) {
    const plays = capture.plays;
    const ev = { t0p: [], t0a: [[0, 15]], t2p: [], na: [[0, 15]] };
    const r = new Array(16).fill(0);
    const first = new Map();
    let envAt = -1, envPlay = null;
    const envPer = () => (r[11] | (r[12] << 8) || 1) / gen.ym_clock;
    const level = (t) => (envAt < 0 ? 0 : Math.max(0, 31 - Math.floor((t - envAt) / envPer() + 1e-9)));
    const derive = (t) => {
        const toneOn = !(r[7] & 1);
        let t0a = 15;
        if (toneOn && r[8] === 15) t0a = gen.tone_att;
        else if (toneOn && r[8] !== 0) t0a = null;      // (a level the ported effects don't use)
        const noisy = [0, 1, 2].filter((c) => !(r[7] & (8 << c)) && r[8 + c] !== 0);
        const env = noisy.filter((c) => r[8 + c] === 0x10);
        let na = null;
        if (!noisy.length) na = 15;
        else if (env.length === 3) na = gen.att3[level(t)];
        else if (env.length === 2 && noisy.length === 2 && !env.includes(0)) na = gen.att2[level(t)];
        return { t0a, na };
    };
    const playAt = (t) => plays.findLastIndex((p) => p.t <= t);
    let state = derive(0), timer = -1, ticks = 0, last = 0;
    const push = (name, t, v, tag) => {
        const l = ev[name];
        if (name === "t0p" || name === "t2p" || l[l.length - 1][1] !== v) l.push([t, v, tag]);
    };
    const steps = (from, to) => {
        if (envAt < 0) return;
        for (let k = Math.max(1, Math.floor((from - envAt) / envPer()) + 1); k <= 31; k++) {
            const t = envAt + k * envPer();
            if (t > to) break;
            state = derive(t);
            push("na", t, state.na, { env: envPlay });
        }
    };
    ev.t0p.push([0, 0, null]);
    ev.t2p.push([0, 0, null]);
    const writes = capture.writes;
    for (let w = 0; w < writes.length; w++) {
        const [tw, reg, val, pc] = writes[w];
        steps(last, tw);
        last = tw;
        const i = playAt(tw);
        const tick = ticking(pc);
        // a timer play's own start begins its ticks
        if (!tick && i >= 0 && i !== timer && stTick(plays[i].effect) && tw - plays[i].t < START) [timer, ticks] = [i, 0];
        r[reg] = val;
        if (reg === 13) [envAt, envPlay] = [tw, i];
        const tag = tick ? { tick: timer } : { start: i };
        if (reg === 1) {
            if (tick && timer >= 0) {
                ticks++;
                if (!first.has(timer)) first.set(timer, tw);
            }
            const k = tick && timer >= 0 && effect(plays[timer].effect).kind === "sweep" ? effect(plays[timer].effect).k : 1;
            if (!tick || ticks % k === 0) push("t0p", tw, r[0] | ((r[1] & 3) << 8), tag);
        }
        if (reg === 6) push("t2p", tw, Math.max(r[6] & 31, 1), tag);
        // the levels once a burst of writes (an effect's start) is done
        if (w + 1 < writes.length && writes[w + 1][0] - tw < 40e-6) continue;
        state = derive(tw);
        push("t0a", tw, state.t0a, tag);
        push("na", tw, state.na, tag);
    }
    steps(last, last + 10);
    // each timer play's first tick against the port's, a tick after its start:
    // how much later the port's ticks come
    const late = new Map();
    for (const [i, t] of first) {
        const p = plays[i], T = stTick(p.effect);
        const ticksBefore = effect(p.effect).kind === "two" ? 31 : 0;
        late.set(i, T - (t - p.t - ticksBefore * T));
    }
    return { ev, late };
}

// Writes a few microseconds apart (a period's two bytes) as one: the last.
function settle(list, gap = 40e-6) {
    const out = [];
    for (const e of list) {
        if (out.length && e[0] - out[out.length - 1][0] < gap) out[out.length - 1] = e;
        else out.push(e);
    }
    return out;
}
const changes = (list) => list.filter((e, i) => !i || e[1] !== list[i - 1][1]);
const at = (list, t) => {
    let v = list[0][1];
    for (const e of list) if (e[0] <= t) v = e[1];
    return v;
};

for (const file of captures) {
    const capture = JSON.parse(fs.readFileSync(file, "utf8"));
    const m = await machine();
    m.chip.writes.length = 0;
    const start = m.now() + HZ / 10;
    const injected = [];
    for (const p of capture.plays) {
        await m.runTo(start + p.t * HZ);
        injected.push((await m.call(sym.sfx_start, p.effect, p.count) - start) / HZ);
    }
    await m.runTo(start + (capture.plays[capture.plays.length - 1].t + 4) * HZ);
    const sn = snEvents(m.chip.writes, start);
    const port = {
        t0p: settle(sn.t0p), t2p: settle(sn.t2p),
        t0a: changes([[0, 15], ...sn.t0a]), na: changes([[0, 15], ...sn.na]),
    };
    const { ev: st, late } = stTimeline(capture);
    const plays = capture.plays.map((p, i) => ({ ...p, port: injected[i], ported: !!effect(p.effect).ported }));
    let compared = 0;
    for (let i = 0; i < plays.length; i++) {
        if (!plays[i].ported || (i > 0 && plays[i - 1].ported)) continue;
        let j = i;
        while (j + 1 < plays.length && plays[j + 1].ported) j++;
        const t0 = plays[i].t, t1 = j + 1 < plays.length ? plays[j + 1].t : plays[j].t + 4;
        const where = `${path.basename(path.dirname(file))} plays ${i}-${j} (effects ${plays.slice(i, j + 1).map((p) => p.effect).join(",")})`;
        // the ST's moment as the port's, and the port's as the ST's, by the latest play
        const toPort = (t) => {
            const q = plays[Math.max(i, plays.findLastIndex((p) => p.t <= t))];
            return t + (q.port - q.t);
        };
        const fromPort = (t) => {
            const q = plays[Math.max(i, plays.findLastIndex((p) => p.port <= t))];
            return t - (q.port - q.t);
        };
        // where each change should come on the port, and how far from it
        const expect = (name, e) => {
            const tag = e[2] ?? {};
            if (tag.start !== undefined) return [toPort(e[0]), -SLACK, SLACK];
            if (tag.env !== undefined) {
                const spread = gen.field + SLACK + 0.01 * (e[0] - plays[tag.env].t);
                return [toPort(e[0]), -spread, spread];
            }
            const q = tag.tick ?? -1;
            const shift = late.get(q) ?? 0;
            const k = q >= 0 && effect(plays[q].effect).kind === "sweep" ? effect(plays[q].effect).k : 1;
            const end = name === "t0p" ? 0 : (k - 1) * stTick(plays[q]?.effect ?? 0);
            const field = name === "na" ? gen.field : 0;
            return [toPort(e[0]) + shift, -SLACK, SLACK + end + field];
        };
        for (const name of ["t0p", "t0a", "t2p", "na"]) {
            // the levels as each chip stood once the window's first play had
            // started (what came before it may differ), then their changes;
            // every period written
            const levels = name === "t0a" || name === "na";
            const from = levels ? t0 + START : t0;
            if (levels) {
                const a0 = at(st[name], from), b0 = at(port[name], toPort(from));
                if (a0 !== b0) fail(`${where}: ${name} ${b0} after the start, the ST's ${a0}`);
            }
            const a = st[name].filter((e) => e[0] > from && e[0] < t1);
            const b = port[name].filter((e) => fromPort(e[0]) > from && fromPort(e[0]) < t1 - SLACK);
            if (a.some((e) => e[1] === null)) {
                fail(`${where}: the ST's ${name} takes a level the port has no record of`);
                continue;
            }
            if (show) {
                console.log(`${where} ${name} ST:   ${a.map((e) => `${e[1]}@${(e[0] - t0).toFixed(4)}`).join(" ")}`);
                console.log(`${where} ${name} port: ${b.map((e) => `${e[1]}@${(fromPort(e[0]) - t0).toFixed(4)}`).join(" ")}`);
            }
            for (let k = 0; k < Math.max(a.length, b.length); k++) {
                const x = a[k], y = b[k];
                if (!x || !y || x[1] !== y[1]) {
                    fail(`${where}: ${name}'s change ${k}: the ST's ${x ? `${x[1]} at ${(x[0] - t0).toFixed(4)}s` : "none"}, the port's ${y ? `${y[1]} at ${(fromPort(y[0]) - t0).toFixed(4)}s` : "none"}`);
                    break;
                }
                const [want, lo, hi] = expect(name, x);
                const dt = y[0] - want;
                if (dt < lo || dt > hi) {
                    fail(`${where}: ${name}'s change ${k} (${x[1]}) ${(dt * 1000).toFixed(2)}ms from where the ST's says, ${(x[0] - t0).toFixed(4)}s`);
                    break;
                }
                compared++;
            }
        }
    }
    for (const [t, v] of sn.t1a.concat(sn.t2a)) if (v !== 15) fail(`tone 1 or 2 at attenuation ${v}, ${t.toFixed(3)}s`);
    for (const [t, v] of sn.nctl) if (v !== 7) fail(`the noise's control ${v}, ${t.toFixed(3)}s`);
    console.log(`sfxcheck: ${path.relative(root, file)}: ${plays.length} plays, ${compared} changes matched`);
}

// The gates, on a machine of their own.
{
    const m = await machine();
    const LASER = 20;
    const written = async (secs) => {
        const n = m.chip.writes.length;
        await m.runTo(m.now() + secs * HZ);
        return m.chip.writes.length - n;
    };
    m.ram[sym.sound_on] = 0;
    await m.call(sym.sfx_start, LASER, 1);
    if (await written(0.1)) fail("an effect with the sound off");
    m.ram[sym.sound_on] = 0xff;
    const bytes = 1000;
    m.ram.set([bytes & 0xff, bytes >> 8, 0, 0], sym.sample_left);
    await m.call(sym.sfx_start, LASER, 1);
    if (await written(0.05)) fail("an effect while a sample plays");
    const from = m.now() - 0.05 * HZ;
    while (m.ram[sym.sample_left] | m.ram[sym.sample_left + 1]) await m.runTo(m.now() + 1000);
    const took = (m.now() - from) / HZ, want = bytes / 6144;
    if (Math.abs(took - want) > gen.field) fail(`a sample's ${bytes} bytes counted down in ${took.toFixed(3)}s, not ${want.toFixed(3)}s`);
    await m.call(sym.sfx_start, LASER, 1);
    if (!(await written(0.05))) fail("no effect once the sample's done");
    // a sample's start (speech, in the logic's bank, which the engine left
    // paged): the laser's tone and the noise off at once, its ticks stopped
    m.ram.set([0x80, 0x00], sym.sample_len);
    const n = m.chip.writes.length;
    await m.call(sym.speech);
    await m.runTo(m.now() + 0.3 * HZ);
    const after = m.chip.writes.slice(n).map((w) => w[1]);
    if (after.join() !== [0x9f, 0xff].join()) fail(`a sample's start wrote ${after.map((v) => v.toString(16)).join(" ")}`);
    m.ram.set([0, 0, 0, 0], sym.sample_left);
    // the fastest sweeps, a key held: every tick on time
    m.tm.keyDown("ArrowLeft");
    await m.runTo(m.now() + 0.1 * HZ);
    for (const e of gen.effects.filter((e) => e.ported && e.kind === "sweep" && e.k > 1)) {
        const k = m.chip.writes.length;
        const t = await m.call(sym.sfx_start, e.effect, 1);
        await m.runTo(m.now() + 0.1 * HZ);
        // a tick the interrupt holds off comes late, but one the VIA's flag
        // lost puts every tick after it a tick behind its time
        const ticks = settle(snEvents(m.chip.writes.slice(k), t).t0p).map((x) => x[0]);
        const tick = (e.latch + 2) / gen.via_hz;
        const off = ticks.map((x, i) => x - i * tick);
        const base = Math.min(...off);
        const lost = off.findIndex((x) => x - base > 0.9 * tick);
        if (lost >= 0 || base > 1.9 * tick) fail(`effect ${e.effect} with a key held: a tick lost by tick ${lost}`);
        if (ticks.length !== Math.ceil((e.end - e.start) / (e.step * e.k)) - 1) fail(`effect ${e.effect} with a key held: ${ticks.length} ticks`);
    }
    m.tm.keyUp("ArrowLeft");
    console.log("sfxcheck: the gates checked");
}

if (bad) {
    console.log(`sfxcheck: ${bad} failed`);
    process.exit(1);
}
console.log("sfxcheck: ok");
