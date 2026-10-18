// Where the disc's erase goes, a frame at a time, holding keys:
//
//   node tools/eraseprof.mjs [SECONDS] [KEYS] [--missile] [--build DIR]
//
// KEYS as tools/listprof.mjs takes them. --missile launches a missile (L)
// as the count starts, and the missile view's frames are counted apart.
// Each frame's erase (frame to frame.erased) is split into its parts: the
// erase list's entries by what drew them (the objects' lines, the objects'
// boxes, the gunsight's lines, and the lines the step's logic drew: the
// bolt and the shots), the list's own work, a window cleared whole, and
// the dots; and the missile view's window as win_draw puts it back. For
// the objects whose lines are drawn again it takes the box they lie in,
// and what clearing it would cost by decision 20's model (40 + rows (10 +
// 6 bytes)), to set against what drawing them again did. It counts too
// the objects' lines drawn past the window they're clipped to, which no
// box would erase. --build reads DIR's starglider.ssd and its symbols.
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const build = opt("--build", "build");
const missile = args.includes("--missile");
const pos = args.filter((a) => !a.startsWith("--"));
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const { loadDisc } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const sym = loadSymbols(path.join(root, build, "starglider.json"));
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log; console.log = () => {}; await tm.runUntilInput(); console.log = q;
const cpu = tm.processor, ram = cpu.ramRomOs;          // (shadow RAM is at &8000 on in jsbeeb's)
loadDisc(tm, path.join(root, build, "starglider.ssd"), sym);
await tm.runFor(14 * 2000000);
const keys = (pos[1] ?? "").split(",").filter(Boolean);
for (const k of keys) tm.keyDown(k);
if (keys.length) await tm.runFor(2 * 2000000);

// an erase list's field of entry i on screen s (src/memory.6502)
const field = (f, s, i) => ram[0x8000 + sym.ERASE_LIST + (2 * f + s) * 256 + i];
const model = (b) => 40 + (b.y1 - b.y0 + 1) * (10 + 6 * ((b.x1 >> 2) - (b.x0 >> 2) + 1));
// by screen: what drew each entry of its list, and each object's lines' box
const drawn = [new Map(), new Map()];
const boxes = [new Map(), new Map()];
let owner = null, buf = 0, nobj = 0, outside = 0;
let frame = null, entry = null, winAt = 0;
const frames = [];
const add = (o, k, v) => { o[k] = (o[k] ?? 0) + v; };
const endEntry = (t) => {
    if (!entry) return;
    const kind = entry.box ? "objects' boxes" : entry.owner.startsWith("obj") ? "objects' lines" : entry.owner;
    add(frame.parts, kind, t - entry.t);
    if (entry.owner.startsWith("obj")) add(entry.box ? frame.boxed : frame.replay, entry.owner, t - entry.t);
    entry = null;
};
const at = new Map([
    [sym.frame, "frame"], [sym.erase_screen, "erase"], [sym["erase_screen.each"], "each"],
    [sym["erase_screen.done"], "done"], [sym.window_clear, "clear"], [sym["screen_erase.dots"] ?? sym.dots_erase, "dots"],
    [sym["frame.erased"], "erased"], [sym.view_under, "under"], [sym.draw_shape, "shape"],
    [sym.line_plot, "line"], [sym.draw_end, "end"], [sym.erase_more, "more"],
    [sym.win_draw, "win"], [sym.dots_draw, "dots_draw"],
]);
cpu.debugInstruction.add((pc) => {
    const m = at.get(pc);
    if (m === undefined) return false;
    if (pc >= 0x8000 && pc < 0xc000 && (cpu.romsel & 15) !== sym.BANK_PIC) return false;
    const t = tm.elapsedCycles;
    switch (m) {
        case "frame":
            frame = { parts: {}, replay: {}, boxed: {}, objects: [], mv: ram[sym.mv_render] };
            break;
        case "erase":
            if (!frame) break;
            buf = ram[sym.draw_buffer];
            frame.t = t;
            break;
        case "each":
            if (!frame) break;
            endEntry(t);
            entry = { t, owner: drawn[buf].get(cpu.x) ?? "unknown", box: sym.LINE_BOX !== undefined && field(sym.EF_CODE, buf, cpu.x) === sym.LINE_BOX };
            break;
        case "done":
            if (frame) endEntry(t);
            break;
        case "clear":
            if (frame && frame.dots === undefined) frame.cleared = t;
            break;
        case "dots":
            if (!frame) break;
            endEntry(t);
            frame.dots = t;
            if (frame.cleared !== undefined) add(frame.parts, "a clear", t - frame.cleared);
            frame.parts["the list"] = t - frame.t - Object.values(frame.parts).reduce((a, b) => a + b, 0);
            // what this screen drew last, now erased
            for (const [o, b] of boxes[buf]) {
                if (frame.replay[o] !== undefined) frame.objects.push({ erase: frame.replay[o], model: model(b), lines: b.n });
                else if (frame.boxed[o] !== undefined) frame.objects.push({ erase: frame.boxed[o], lines: b.n, boxed: true });
            }
            drawn[buf].clear();
            boxes[buf].clear();
            break;
        case "erased":
            if (frame) frame.parts.dots = t - frame.dots;
            break;
        case "under":
            owner = "the sight's lines";
            break;
        case "shape":
            owner = `obj${nobj++}`;
            break;
        case "end":
            owner = null;
            break;
        case "more":
            owner = "the step's lines";
            break;
        case "line": {
            if (owner === null) break;
            const s = ram[sym.draw_buffer];
            drawn[s].set(ram[sym.erase_i], owner);
            if (!owner.startsWith("obj")) break;
            const x0 = ram[sym.line_x0] | (ram[sym.line_x0 + 1] << 8), x1 = ram[sym.line_x1] | (ram[sym.line_x1 + 1] << 8);
            const y0 = ram[sym.line_y0], y1 = ram[sym.line_y1];
            const b = boxes[s].get(owner) ?? { x0: 999, x1: -1, y0: 999, y1: -1, n: 0 };
            b.x0 = Math.min(b.x0, x0, x1); b.x1 = Math.max(b.x1, x0, x1);
            b.y0 = Math.min(b.y0, y0, y1); b.y1 = Math.max(b.y1, y0, y1);
            b.n++;
            boxes[s].set(owner, b);
            const open = ram[sym.mv_render] && !ram[sym.m_iris];
            const [wx0, wx1, wy0, wy1] = open ? [sym.MV_XMIN, sym.MV_XMAX, sym.MV_YMIN, sym.MV_YMAX]
                : [sym.VIEW_XMIN, sym.VIEW_XMAX, sym.VIEW_YMIN, sym.VIEW_YMAX];
            if (Math.min(x0, x1) < wx0 || Math.max(x0, x1) > wx1 || Math.min(y0, y1) < wy0 || Math.max(y0, y1) > wy1) outside++;
            break;
        }
        case "win":
            winAt = t;
            break;
        case "dots_draw":
            if (frame && winAt) { frame.window = t - winAt; winAt = 0; }
            if (frame && frame.parts.dots !== undefined) { frames.push(frame); frame = null; }
            break;
    }
    return false;
});
const secs = Number(pos[0] ?? 20);
if (missile) { tm.keyDown("KeyL"); await tm.runFor(0.3 * 2000000); tm.keyUp("KeyL"); }
await tm.runFor(secs * 2000000);
const sum = (xs, f) => xs.reduce((a, o) => a + f(o), 0);
const report = (name, fs) => {
    if (!fs.length) return;
    const n = fs.length, sums = {};
    for (const f of fs) for (const [k, v] of Object.entries(f.parts)) add(sums, k, v);
    console.log(`${name}: ${n} frames, the erase ${Math.round(sum(Object.values(sums), (v) => v) / n)} a frame: ` +
        Object.entries(sums).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${Math.round(v / n)}`).join(", "));
    const win = fs.filter((f) => f.window !== undefined);
    if (win.length) console.log(`  the window put back: ${Math.round(sum(win, (f) => f.window) / win.length)} a frame`);
    const obs = fs.flatMap((f) => f.objects), drawn = obs.filter((o) => !o.boxed), boxed = obs.filter((o) => o.boxed);
    if (!obs.length) return;
    console.log(`  objects erased: ${(obs.length / n).toFixed(2)} a frame, ${(sum(obs, (o) => o.lines) / obs.length).toFixed(1)} lines each, ` +
        `${boxed.length} of ${obs.length} by their boxes, ${Math.round(sum(boxed, (o) => o.erase) / (boxed.length || 1))} each`);
    if (drawn.length) console.log(`  their lines drawn again: ${Math.round(sum(drawn, (o) => o.erase) / n)} a frame, ` +
        `${Math.round(sum(drawn, (o) => o.erase) / sum(drawn, (o) => o.lines))} a line; by decision 20's model, the cheaper of ` +
        `that and the box ${Math.round(sum(drawn, (o) => Math.min(o.erase, o.model)) / n)} a frame`);
};
console.log(`objects' lines past the window: ${outside}`);
report("flying", frames.filter((f) => !f.mv));
report("the missile view", frames.filter((f) => f.mv));
process.exit(0);
