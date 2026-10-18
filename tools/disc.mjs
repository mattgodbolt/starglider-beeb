// The disc's files, put where !BOOT (src/main.6502) puts them, for the
// tools that run the program on jsbeeb's TestMachine without booting:
// SHAPES and WORLD in their banks, TABLES and CODE2 staged in bank 7,
// the cockpit in main RAM's screen, and the disc in the drive. Then run
// from the symbol start.
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
    tm.loadDiscData(fs.readFileSync(path));         // in the drive, for the game's own reader
    const cpu = tm.processor;
    const ram = cpu.ramRomOs;
    const bank = (n) => cpu.romOffset + n * 16384;
    const files = ssdFiles(path);
    ram.set(files.SG, 0x0e00);
    ram.set(files.SHAPES, bank(sym.BANK_SHAPES));
    ram.set(files.WORLD, bank(sym.BANK_WORLD));
    ram.set(files.TABLES, bank(sym.BANK_STAGE) + (sym.TABLES_AT - 0x8000));
    ram.set(files.CODE2, bank(sym.BANK_STAGE) + (sym.CODE2_AT - 0x8000));
    ram.set(files.COCKPIT, sym.SCREEN);
    cpu.pc = sym.start;
}
