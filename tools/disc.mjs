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

// The field as the CRTC makes it for the disc (engine.6502's FIELD_US:
// MODE 1's rows, with screen_mode's interlace off), in 2MHz cycles, which
// tools/fieldcheck.mjs measures on jsbeeb's full video. The TestMachine
// has no CRTC: its field is a count of cycles, the MOS's interlaced 312.5
// lines unless it's told.
export const fieldCycles = (sym) => 2 * sym.FIELD_US;

export function loadDisc(tm, path, sym) {
    tm.loadDiscData(fs.readFileSync(path));
    const cpu = tm.processor;
    cpu.video.fieldCycles = fieldCycles(sym);
    cpu.ramRomOs.set(ssdFiles(path).SG, 0x0e00);
    cpu.pc = sym.start;
}

// From the start to the game: the front end's title waiting for a key
// (src/front.6502's front_title), SPACE pressed for long enough that its
// scan of the keys, a field apart, sees it, and on to the engine, once a
// game's start has loaded flight's files back (src/front_main.6502).
export async function toGame(tm, sym) {
    await tm.runUntilAddress(sym["front_title.poll"], 60, { bank: sym.BANK_PIC });
    tm.keyDown("Space");
    await tm.runFor(0.1 * 2000000);
    tm.keyUp("Space");
    await tm.runUntilAddress(sym.engine_run, 60);
}
