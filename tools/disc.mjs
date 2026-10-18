// The disc in jsbeeb's drive and SG where !BOOT (src/main.6502) puts it,
// for the tools that run the program on jsbeeb's TestMachine without
// booting; SG loads the rest itself, with its own reader. Then run from
// the symbol start.
import fs from "node:fs";

export function ssdFiles(path) {
    const ssd = fs.readFileSync(path);
    const files = {};
    for (let i = 0; i < ssd[0x105] / 8; i++) {
        const name = ssd.subarray(8 + i * 8, 15 + i * 8).toString("latin1").trim();
        const o = 0x108 + i * 8;
        const len = ssd[o + 4] | (ssd[o + 5] << 8) | (((ssd[o + 6] >> 4) & 3) << 16);
        const sector = ssd[o + 7] | ((ssd[o + 6] & 3) << 8);
        files[name] = ssd.subarray(sector * 256, sector * 256 + len);
    }
    return files;
}

export function loadDisc(tm, path, sym) {
    tm.loadDiscData(fs.readFileSync(path));
    const cpu = tm.processor;
    cpu.ramRomOs.set(ssdFiles(path).SG, 0x0e00);
    cpu.pc = sym.start;
}
