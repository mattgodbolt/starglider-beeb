// Clare Edgeley's speech on the disc (decision 5), on jsbeeb's Master:
// each clip played through the logic's own entry (speech, with the ST's
// sample_clip and length), and the chip's writes against the levels
// tools/mkspeech.py packed: tone 1 a carrier (period 1), then each level
// in order on its attenuation, and nothing else written, at SPEECH_RATE
// over the clip, each sample within JITTER of its moment; the clip's end
// (tone 1 off, sample_left 0) at the ST's length at 6144 a second. With a
// key held, whose scan is the vertical sync's longest work, a clip keeps
// its time, its samples within a scan of theirs and their line at the
// rate they keep without (the late ticks' debts paid). sample_stop ends a
// clip at the player's next count. The palette split stays in its window
// while a clip plays. And a WAV of each clip as the chip played it, into
// build/speech, for listening (tools/st_samples.py --wav writes the ST's).
//
//   node tools/speechcheck.mjs
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { HZ, sym, machine, snEvents } = await import(pathToFileURL(path.join(root, "tools/soundbeeb.mjs")).href);
const gen = JSON.parse(fs.readFileSync(path.join(root, "build/gen/speech.json"), "utf8"));
const ST_HZ = 6144;
// a tick waiting on the split: the guard's 256us window, the split's
// interrupt, and the tick's own way to its sample
const JITTER = 350e-6;
const SCAN = 900e-6;                    // ... with a key held
const RATE_SLACK = 0.002;
// a key held: the samples' line at the rate they keep with none, which a
// late tick's count a microsecond out (SPEECH_LATE's), once a field, would
// tilt by twice this
const HELD_SLACK = 2.5e-5;
const STEP = 60e-6;                     // the line's move from field to field

let bad = 0;
const fail = (what) => {
    bad++;
    if (bad <= 20) console.log(`speechcheck: ${what}`);
};

const m = await machine();
// the split's lateness: from the vertical sync's start to the split's first
// palette write, by its own code (engine.6502's irq_handler)
let syncAt = null, splits = [];
const setVBlankInt = m.cpu.sysvia.setVBlankInt;
m.cpu.sysvia.setVBlankInt = function (level) {
    if (level) syncAt = m.now();
    return setVBlankInt.call(this, level);
};
m.cpu.debugWrite.add((addr) => {
    if (addr !== sym.ula_pal || syncAt === null) return false;
    const pc = m.cpu.oldPcArray[m.cpu.oldPcIndex];
    if (pc >= sym.irq_handler && pc < sym["irq_handler.not_split"]) {
        splits.push(m.now() - syncAt);
        syncAt = null;
    }
    return false;
});

// clip n (from 1) through speech, with the ST's length; its writes
async function play(n, length, during) {
    m.ram[sym.sample_clip] = n;
    m.ram.set([length & 0xff, length >> 8], sym.sample_len);
    const from = m.chip.writes.length;
    const t0 = await m.call(sym.speech);
    if (during) await during(t0);
    while (m.ram[sym.sample_left] | m.ram[sym.sample_left + 1]) await m.runTo(m.now() + 2000);
    await m.runTo(m.now() + 0.01 * HZ);
    return { t0, writes: m.chip.writes.slice(from) };
}

function check(name, clip, { t0, writes }, jitter) {
    const ev = snEvents(writes, t0);
    const levels = ev.t1a;
    const want = clip.levels;
    // the start: the effects silenced, tone 1 a carrier; then its levels
    const head = writes.slice(0, 4).map((w) => w[1]);
    if (head.join() !== [0x9f, 0xff, 0xa1, 0x00].join()) fail(`${name}: starts ${head.map((v) => v.toString(16)).join(" ")}`);
    const others = Object.entries(ev).filter(([k, l]) => k !== "t1a" && k !== "t1p" && l.length > (k === "t0a" || k === "na" ? 1 : 0));
    if (others.length) fail(`${name}: writes ${others.map(([k]) => k).join(", ")} as it plays`);
    const off = levels[levels.length - 1];
    const got = levels.slice(0, -1).map((e) => e[1]);
    if (off[1] !== 15) fail(`${name}: doesn't end with tone 1 off`);
    if (got.length !== want.length || got.some((v, i) => v !== want[i])) {
        const i = got.findIndex((v, k) => v !== want[k]);
        fail(`${name}: ${got.length} levels, not ${want.length}; the first that differs, ${i}`);
        return;
    }
    // the rate, and each sample against it
    const t = levels.slice(0, -1).map((e) => e[0]);
    const period = (t[t.length - 1] - t[0]) / (t.length - 1);
    // ... and the samples' least-squares line, which a scan's lateness at
    // either end doesn't tilt
    const mid = (t.length - 1) / 2, tmean = t.reduce((a, b) => a + b, 0) / t.length;
    const fit = t.reduce((a, x, i) => a + (i - mid) * (x - tmean), 0) / t.reduce((a, _, i) => a + (i - mid) ** 2, 0);
    if (Math.abs(period * gen.rate - 1) > RATE_SLACK) fail(`${name}: ${(1 / period).toFixed(1)} samples a second`);
    // each sample against the rate's line through the samples a field
    // either side of it (their median), which drifts by a few microseconds
    // a field with what the catching up after the vertical sync gives back
    const dev = t.map((x, i) => x - (t[0] + i * period));
    const field = Math.round(gen.rate / 50);
    let worst = 0;
    for (let i = 0; i < t.length; i++) {
        const near = dev.slice(Math.max(0, i - field), i + field + 1).sort((a, b) => a - b);
        worst = Math.max(worst, Math.abs(dev[i] - near[near.length >> 1]));
    }
    if (worst > jitter) fail(`${name}: a sample ${(worst * 1e6).toFixed(0)}us from its moment`);
    // and that line steady from field to field: a tick that took its count
    // wrongly would move every sample after it
    const medians = [];
    for (let i = 0; i + field <= dev.length; i += field) {
        const block = dev.slice(i, i + field).sort((a, b) => a - b);
        medians.push(block[block.length >> 1]);
    }
    const step = Math.max(0, ...medians.slice(1).map((v, k) => Math.abs(v - medians[k])));
    if (step > STEP) fail(`${name}: its samples move ${(step * 1e6).toFixed(0)}us from one field to the next`);
    // the end, at the ST's length
    const end = clip.played / ST_HZ;
    if (Math.abs(off[0] - end) > 2 / gen.rate + jitter) fail(`${name}: ends at ${off[0].toFixed(4)}s, not ${end.toFixed(4)}s`);
    return { worst, period, step, fit };
}

function wav(file, writes, t0) {
    const rate = 44100;
    const ev = snEvents(writes, t0).t1a;
    const end = ev[ev.length - 1][0];
    const n = Math.ceil(end * rate);
    const amp = (k) => (k === 15 ? 0 : 10 ** (-k / 10));
    const out = new Float64Array(n);
    let j = 0, level = 0;
    for (let i = 0; i < n; i++) {
        while (j < ev.length && ev[j][0] <= i / rate) level = amp(ev[j++][1]);
        out[i] = level;
    }
    const mean = out.reduce((a, b) => a + b, 0) / n;
    const buf = Buffer.alloc(44 + 2 * n);
    buf.write("RIFF", 0); buf.writeUInt32LE(36 + 2 * n, 4); buf.write("WAVEfmt ", 8);
    buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(1, 22);
    buf.writeUInt32LE(rate, 24); buf.writeUInt32LE(2 * rate, 28); buf.writeUInt16LE(2, 32); buf.writeUInt16LE(16, 34);
    buf.write("data", 36); buf.writeUInt32LE(2 * n, 40);
    for (let i = 0; i < n; i++) buf.writeInt16LE(Math.max(-32767, Math.min(32767, Math.round((out[i] - mean) * 30000))), 44 + 2 * i);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, buf);
}

const report = [];
let free = null;
for (const [i, clip] of gen.clips.entries()) {
    splits = [];
    const run = await play(i + 1, clip.played);
    const r = check(clip.name, clip, run, JITTER);
    if (i === 0) free = r;
    wav(path.join(root, "build/speech", `${clip.name}.wav`), run.writes, run.t0);
    const least = Math.min(...splits);
    const late = splits.filter((d) => d - least > 40).length;
    if (late) fail(`${clip.name}: ${late} of ${splits.length} splits late`);
    if (r) report.push(`${clip.name} ${(1 / r.period).toFixed(1)}Hz, worst ${(r.worst * 1e6).toFixed(0)}us, steps ${(r.step * 1e6).toFixed(0)}us`);
}
// a key held: its time kept
m.tm.keyDown("ArrowLeft");
await m.runTo(m.now() + 0.05 * HZ);
{
    const r = check("clare1, a key held", gen.clips[0], await play(1, gen.clips[0].played), SCAN);
    if (r) report.push(`a key held ${(1 / r.period).toFixed(1)}Hz, worst ${(r.worst * 1e6).toFixed(0)}us, steps ${(r.step * 1e6).toFixed(0)}us`);
    if (r && free && Math.abs(r.fit / free.fit - 1) > HELD_SLACK)
        fail(`a key held: ${(1 / r.fit).toFixed(2)} samples a second on their line, not ${(1 / free.fit).toFixed(2)}`);
}
m.tm.keyUp("ArrowLeft");
// Q's sample_stop: the clip ends at the player's next count
{
    let stopped = 0;
    const run = await play(2, gen.clips[1].played, async () => {
        await m.runTo(m.now() + 0.3 * HZ);
        stopped = await m.call(sym.sample_stop);
    });
    const ev = snEvents(run.writes, stopped).t1a;
    const off = ev[ev.length - 1];
    if (off[1] !== 15 || off[0] < 0 || off[0] > 3 / gen.rate) fail(`sample_stop: the clip ends ${(off[0] * 1e3).toFixed(2)}ms on`);
}
console.log(`speechcheck: ${gen.clips.length} clips, ${report.join("; ")}`);
if (bad) {
    console.log(`speechcheck: ${bad} failed`);
    process.exit(1);
}
console.log("speechcheck: ok, the WAVs in build/speech");
process.exit(0);
