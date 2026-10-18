// The controls (src/input.6502, decision 6) on the disc, on jsbeeb's
// Master. The stick, moved, must move the accumulators the logic steers
// by as the ST's mouse moves them: from its centre to either end and back
// is the turn's or the climb's clamp and back, the climb the speed's with
// the second button held, and a count's move is noise. Then each BBC key
// in input.6502's key_map, held, must set its ST key's state and the
// latch at the vertical sync's next read, and clear the state once let
// go; and the joysticks' buttons the same as the ST's mouse buttons.
//
//   node tools/inputcheck.mjs
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { loadDisc } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const sym = loadSymbols(path.join(root, "build/starglider.json"));
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = q;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
// the stick's axes: what the ADC converts (0 an end, &FFFF the other)
const axis = [0x8000, 0x8000];
for (const ch of [0, 1]) cpu.adconverter.setChannelSource(ch, { getValue: (c) => axis[c], dispose() {} });
loadDisc(tm, path.join(root, "build/starglider.ssd"), sym);
await tm.runUntilAddress(sym.engine_run, 60);
await tm.runFor(2000000);

let bad = 0;
const fail = (what) => {
    bad++;
    if (bad <= 10) console.log(`inputcheck: ${what}`);
};
const s16 = (a) => {
    const v = ram[a] | (ram[a + 1] << 8);
    return v & 0x8000 ? v - 0x10000 : v;
};
const steps = (n) => tm.runFor(n * 4 * 40000);           // n steps of 4 fields
const expect = (name, want) => {
    const got = s16(sym[name]);
    if (got !== want) fail(`${name} ${got}, not ${want}`);
};

// the stick (the logic adds nothing to the accumulators but the keys,
// none held, and player_flight's clamps: the moves stay within them)
const speed0 = s16(sym.speed_acc);
const moves = [
    [0, 0x0000, "mouse_x", 496],    // right: the turn's clamp
    [0, 0x8000, "mouse_x", 0],
    [0, 0xffff, "mouse_x", -492],   // left, the ADC's 255
    [0, 0x8000, "mouse_x", 0],
    [0, 0x8100, "mouse_x", 0],      // a count: noise
    [0, 0x8000, "mouse_x", 0],
    [1, 0x0000, "mouse_y", 320],    // back: the climb's clamp
    [1, 0x8000, "mouse_y", 0],
];
for (const [ch, v, name, want] of moves) {
    axis[ch] = v;
    await steps(3);
    expect(name, want);
}
cpu.sysvia.setJoystickButton(1, true);                   // the second button: the speed
await steps(2);
axis[1] = 0xffff;                                       // forward: faster
await steps(3);
expect("speed_acc", speed0 - 317);
expect("mouse_y", 0);
axis[1] = 0x8000;
await steps(3);
expect("speed_acc", speed0);
cpu.sysvia.setJoystickButton(1, false);
await steps(2);

// the keys, each read at the vertical sync after it's pressed
const scanned = sym["input_irq.scanned"];
const read = () => tm.runUntilAddress(scanned, 1);
const state = sym.key_state;
let keys = 0;
for (let i = 0; i < sym.KEY_MAP_BYTES; i += 2) {
    const bbc = ram[sym.key_map + i];
    const st = ram[sym.key_map + i + 1];
    const name = `BBC key &${bbc.toString(16)} (ST &${st.toString(16)})`;
    await read();
    cpu.sysvia.keyDownRaw([bbc & 15, bbc >> 4]);
    await read();
    if (ram[state + st] !== 1) fail(`${name}: held, its state is ${ram[state + st]}`);
    if (ram[sym.key_latch] !== st) fail(`${name}: made, the latch is &${ram[sym.key_latch].toString(16)}`);
    cpu.sysvia.keyUpRaw([bbc & 15, bbc >> 4]);
    await read();
    if (ram[state + st] !== 0) fail(`${name}: let go, its state is ${ram[state + st]}`);
    keys++;
}
// the buttons, read after the keys: two reads after each change
for (const [button, st] of [[0, sym.ST_BUTTON_LEFT], [1, sym.ST_BUTTON_RIGHT]]) {
    cpu.sysvia.setJoystickButton(button, true);
    await read();
    await read();
    if (ram[state + st] !== 1) fail(`button ${button + 1}: held, ST key &${st.toString(16)}'s state is ${ram[state + st]}`);
    cpu.sysvia.setJoystickButton(button, false);
    await read();
    await read();
    if (ram[state + st] !== 0) fail(`button ${button + 1}: let go, its state is ${ram[state + st]}`);
}
console.log(`inputcheck: the stick's ${moves.length + 2} moves, ${keys} keys and 2 buttons; ${bad} wrong`);
process.exit(bad ? 1 : 0);
