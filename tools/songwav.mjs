// The title song's candidates as WAVs to listen to (decision 5,
// docs/research/song.md): each of tools/mksong.py's SN76489 write files
// through jsbeeb's own chip, resampler and audio path, and the Spectrum's
// AY writes (zx_ay.json) through a model of the AY.
//
//   node tools/songwav.mjs DIR [NAME...]
//
// renders DIR/NAME.json for each NAME (mksong.py's five if none is
// given): an SN one as DIR/wav/NAME_chip.wav (the chip's output with
// nothing after it: what the conversion itself sounds like) and
// DIR/wav/NAME_speaker.wav (jsbeeb's model of the Master's board and its
// own speaker, jsbeeb's default output: what a Master in its case plays),
// an AY one as DIR/wav/NAME.wav; all 16-bit at 44.1 kHz, each scaled to
// the same peak. It prints each one's loudness before the scaling, as the
// RMS in dB against one tone channel at full volume, so the candidates'
// levels on the BBC can be compared.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = process.cwd();
const jsbeeb = (f) => pathToFileURL(path.join(root, "node_modules/jsbeeb/src", f)).href;
const { SoundChip } = await import(jsbeeb("soundchip.js"));
const { PolyphaseResampler } = await import(jsbeeb("resampler.js"));
const { outputStages, AudioOutputs, ResamplerCutoffOfOutputRate, ResamplerTaps } = await import(
    jsbeeb("audio-output.js")
);

const OUT_HZ = 44100;
const TAIL_S = 0.3;                 // for the filters to ring out
const QUANTUM = 512;
const PEAK = 0.89;                  // -1 dBFS
const CHANNEL_RMS = 0.125;          // one tone channel at full volume: a square of 0.25 (jsbeeb's), its AC

// The AY-3-8912's levels for volumes 0-15 against 15's, as tools/zx_speech.py
// has them, scaled as jsbeeb scales one SN channel at full volume.
const AY_LEVELS = [0.0, 0.0137, 0.0205, 0.0291, 0.0423, 0.0618, 0.0847, 0.1369, 0.1691, 0.2647, 0.3527, 0.4499,
    0.5704, 0.6873, 0.8482, 1.0].map((v) => v / 4);

// Renders `inputRate` samples from `fill(buffer, offset, count)`, through
// `filters`, into `seconds` of output at OUT_HZ, as jsbeeb's audio worklet
// does it (web/audio-renderer.js).
function resampled(inputRate, seconds, fill, filters) {
    const resampler = new PolyphaseResampler(inputRate, ResamplerCutoffOfOutputRate * OUT_HZ, {
        taps: ResamplerTaps,
    });
    const ratio = inputRate / OUT_HZ;
    const total = Math.ceil(seconds * OUT_HZ);
    const out = new Float32Array(total);
    let phase = 0;
    for (let pos = 0; pos < total; pos += QUANTUM) {
        const n = Math.min(QUANTUM, total - pos);
        const end = phase + n * ratio;
        const count = Math.floor(end);
        resampler.reserve(count);
        fill(resampler.buffer, resampler.inputOffset, count);
        for (const filter of filters) filter.process(resampler.buffer, resampler.inputOffset, count);
        resampler.read(out.subarray(pos, pos + n), phase, ratio);
        resampler.commit();
        phase = end - count;
    }
    return out;
}

// The SN76489 as jsbeeb has it, written at each write's moment.
function renderSn(song, output) {
    const chip = new SoundChip(null);
    const perCycle = chip.samplesPerCycle;
    if (song.hz !== 2e6) throw new Error("SN writes are timed in the BBC's 2MHz cycles");
    const writes = song.writes;
    let clock = 0;
    let head = 0;
    const fill = (buffer, offset, count) => {
        while (count > 0) {
            const due = head < writes.length ? Math.floor((writes[head][0] - clock) * perCycle) : count;
            const n = Math.min(count, due);
            if (n > 0) {
                chip.renderAt(clock, buffer, offset, n);
                clock += n / perCycle;
                offset += n;
                count -= n;
            } else {
                chip.applyEvent({ kind: "poke", value: writes[head++][1] });
            }
        }
    };
    const stages = outputStages(chip.soundchipFreq, output);
    return resampled(chip.soundchipFreq, song.end / song.hz + TAIL_S, fill, stages);
}

// The envelope's level n steps after register 13 was written (16 steps a
// cycle; shape bits 8 continue, 4 attack, 2 alternate, 1 hold), as
// tools/mksong.py has it.
function envelope(shape, n) {
    if (!(shape & 8)) shape = shape & 4 ? 15 : 9;
    const attack = (shape & 4) !== 0;
    const cycle = Math.floor(n / 16);
    const step = n % 16;
    if (shape & 1 && cycle) return attack !== ((shape & 2) !== 0) ? 15 : 0;
    const up = attack !== ((shape & 2) !== 0 && (cycle & 1) === 1);
    return up ? step : 15 - step;
}

// The AY at an eighth of its clock: a tone of period P flips every P
// steps, the noise (17 bits, fed back from bits 0 and 3) shifts every 2N,
// and the envelope steps every 2E; each channel sounds where its tone and
// its noise are high or turned off by the mixer. A DC blocker as jsbeeb's
// chip has stands for the Spectrum's coupling.
function renderAy(song) {
    const rate = song.ay_hz / 8;
    const perT = rate / song.hz;
    const r = new Uint8Array(16);
    const toneCount = [0, 0, 0];
    const toneOut = [0, 0, 0];
    let noiseCount = 0, noiseHalf = 0, lfsr = 1, envCount = 0, envPos = 0;
    let clock = 0;
    let head = 0;
    const writes = song.writes;
    const alpha = 1 - (2 * Math.PI * (1 / (2 * Math.PI * 10e3 * 4.7e-6))) / rate;
    let prevIn = 0, prevOut = 0;
    const fill = (buffer, offset, count) => {
        for (let i = 0; i < count; i++, clock++) {
            while (head < writes.length && writes[head][0] * perT <= clock) {
                const [, reg, v] = writes[head++];
                r[reg] = v;
                if (reg === 13) envCount = envPos = 0;
            }
            for (let c = 0; c < 3; c++) {
                const p = Math.max(1, r[2 * c] | ((r[2 * c + 1] & 15) << 8));
                if (++toneCount[c] >= p) {
                    toneCount[c] = 0;
                    toneOut[c] ^= 1;
                }
            }
            if (++noiseCount >= Math.max(1, r[6] & 31)) {
                noiseCount = 0;
                noiseHalf ^= 1;
                if (noiseHalf) lfsr = (lfsr >> 1) | (((lfsr ^ (lfsr >> 3)) & 1) << 16);
            }
            if (++envCount >= 2 * Math.max(1, r[11] | (r[12] << 8))) {
                envCount = 0;
                envPos++;
            }
            const env = envelope(r[13], envPos);
            let x = 0;
            for (let c = 0; c < 3; c++) {
                const tone = toneOut[c] | ((r[7] >> c) & 1);
                const noise = (lfsr & 1) | ((r[7] >> (3 + c)) & 1);
                if (tone & noise) x += AY_LEVELS[r[8 + c] & 16 ? env : r[8 + c] & 15];
            }
            prevOut = x - prevIn + alpha * prevOut;
            prevIn = x;
            buffer[offset + i] = prevOut;
        }
    };
    return resampled(rate, song.end / song.hz + TAIL_S, fill, []);
}

function writeWav(file, samples) {
    let peak = 0, sum = 0;
    for (const s of samples) {
        peak = Math.max(peak, Math.abs(s));
        sum += s * s;
    }
    const rms = Math.sqrt(sum / samples.length);
    const gain = peak ? PEAK / peak : 1;
    const n = samples.length;
    const buf = Buffer.alloc(44 + 2 * n);
    buf.write("RIFF", 0);
    buf.writeUInt32LE(36 + 2 * n, 4);
    buf.write("WAVEfmt ", 8);
    buf.writeUInt32LE(16, 16);
    buf.writeUInt16LE(1, 20);
    buf.writeUInt16LE(1, 22);
    buf.writeUInt32LE(OUT_HZ, 24);
    buf.writeUInt32LE(2 * OUT_HZ, 28);
    buf.writeUInt16LE(2, 32);
    buf.writeUInt16LE(16, 34);
    buf.write("data", 36);
    buf.writeUInt32LE(2 * n, 40);
    for (let i = 0; i < n; i++) buf.writeInt16LE(Math.round(samples[i] * gain * 32767), 44 + 2 * i);
    fs.writeFileSync(file, buf);
    return { rms, peak };
}

const [dir = "build/song", ...only] = process.argv.slice(2);
const names = only.length ? only : ["st_4096", "st_6144", "zx_bass", "zx_octave", "zx_ay"];
const wavDir = path.join(dir, "wav");
fs.mkdirSync(wavDir, { recursive: true });
const db = (x) => (20 * Math.log10(x / CHANNEL_RMS)).toFixed(1);
for (const name of names) {
    const song = JSON.parse(fs.readFileSync(path.join(dir, `${name}.json`), "utf8"));
    const seconds = (song.end / song.hz).toFixed(2);
    if (song.chip === "ay") {
        const file = path.join(wavDir, `${name}.wav`);
        const { rms } = writeWav(file, renderAy(song));
        console.log(`${file}: ${seconds} s, RMS ${db(rms)} dB`);
        continue;
    }
    for (const [suffix, output] of [["chip", AudioOutputs.off], ["speaker", AudioOutputs.speaker]]) {
        const file = path.join(wavDir, `${name}_${suffix}.wav`);
        const { rms } = writeWav(file, renderSn(song, output));
        console.log(`${file}: ${seconds} s${suffix === "chip" ? `, RMS ${db(rms)} dB` : ""}`);
    }
}
