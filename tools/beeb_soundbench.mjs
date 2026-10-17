// beeb_soundbench.mjs: time a sample-player interrupt and screen clears on
// jsbeeb's Master 128.
//
//   node tools/beeb_soundbench.mjs WORKDIR [--jsbeeb DIR] [--baron PATH]
//
// Builds tools/beeb_soundbench.6502 once per variant into WORKDIR. For the
// player, the foreground counts in a loop of known length for one emulated
// second, with and without the interrupt; the count lost is the player's share
// of the CPU. For the clears, the routine is called once and its cycles counted.

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : dflt;
};
const work = path.resolve(args[0] ?? "");
if (!args[0]) {
    console.error("usage: node tools/beeb_soundbench.mjs WORKDIR [--jsbeeb DIR] [--baron PATH]");
    process.exit(2);
}
const jsbeebDir = path.resolve(opt("--jsbeeb", path.join(here, "..", "..", "jsbeeb")));
const baron = opt("--baron", process.env.BARON ?? path.join(here, "..", "..", "baron", "build", "src", "baron"));
const { TestMachine } = await import(pathToFileURL(path.join(jsbeebDir, "src", "test-machine.js")).href);

function build(defs) {
    const dir = path.join(work, "snd-" + Object.values(defs).join("-"));
    fs.mkdirSync(dir, { recursive: true });
    const d = Object.entries(defs).flatMap(([k, v]) => ["-D", `${k}=${v}`]);
    const out = execFileSync(baron, ["--warn", "2", ...d, path.join(here, "beeb_soundbench.6502"), "-p", dir], {
        encoding: "utf8",
    });
    const sym = {};
    for (const m of out.matchAll(/([a-z_]+) ([0-9A-F]{4})/g)) sym[m[1]] = parseInt(m[2], 16);
    return { bin: fs.readFileSync(path.join(dir, "SNDBENCH")), sym };
}

const tm = new TestMachine("Master");
await tm.initialise();
const log = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = log;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const boot = tm.snapshot();

function load({ bin, sym }) {
    tm.restore(boot);
    for (let i = 0; i < bin.length; i++) ram[sym.start + i] = bin[i];
    // samples: latch bytes for channel 0's volume, a ramp
    for (let a = 0x1800; a < 0x3000; a++) ram[a] = 0x90 | (a & 15);
}

const SECOND = 2_000_000;
async function countFor(b) {
    load(b);
    cpu.pc = b.sym.init;
    await tm.runUntilAddress(b.sym.fg, 1);
    ram[0x70] = ram[0x71] = ram[0x72] = 0;
    await tm.runFor(SECOND);
    return ram[0x70] | (ram[0x71] << 8) | (ram[0x72] << 16);
}

const results = { player: [], clear: [] };
const base = await countFor(build({ HANDLER: -1, T1: 123, PAGES: 1 }));
log(`foreground alone: ${base} counts in ${SECOND} cycles (${(SECOND / base).toFixed(3)} cycles a count)`);
for (const [rateName, t1] of [
    ["4.0kHz", 248],
    ["6.0kHz", 164],
    ["8.0kHz", 123],
    ["11.0kHz", 89],
]) {
    const rate = 1e6 / (t1 + 2);
    for (const [hName, h] of [
        ["acknowledge only", 0],
        ["a latch byte a sample", 1],
        ["two samples a byte", 2],
    ]) {
        const n = await countFor(build({ HANDLER: h, T1: t1, PAGES: 1 }));
        const share = 1 - n / base;
        const perIrq = (share * SECOND) / rate;
        const perFrame = (share * 40000).toFixed(0);
        results.player.push({ rate, handler: hName, share, perIrq, perFrame: +perFrame });
        log(
            `${rateName} (${rate.toFixed(0)} Hz), ${hName.padEnd(22)}: ${(share * 100).toFixed(1)}% of the CPU, ` +
                `${perIrq.toFixed(1)} cycles an interrupt, ${perFrame} cycles a 50Hz frame`,
        );
    }
}

// Clears, timed from a stub as the line bench does.
for (const pages of [20, 40, 80]) {
    const b = build({ HANDLER: -1, T1: 123, PAGES: pages });
    load(b);
    const stub = 0x0e00;
    [0x78, 0x20, b.sym.clear & 0xff, b.sym.clear >> 8, 0x4c, (stub + 4) & 0xff, (stub + 4) >> 8].forEach(
        (v, i) => (ram[stub + i] = v),
    );
    cpu.pc = stub;
    cpu.s = 0xff;
    const t0 = tm.elapsedCycles;
    await tm.runUntilAddress(stub + 4, 1);
    const cycles = tm.elapsedCycles - t0 - 14; // less SEI, JSR, RTS
    results.clear.push({ bytes: pages * 256, cycles });
    log(`clear ${pages * 256} bytes (${pages} pages, STZ abs,X): ${cycles} cycles, ${(cycles / (pages * 256)).toFixed(2)} a byte`);
}
fs.writeFileSync(path.join(work, "soundbench.json"), JSON.stringify(results, null, 2));
