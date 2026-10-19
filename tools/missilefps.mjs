// The disc's pace through a missile view: a missile launched (L) in flight,
// and each frame drawn until the view has ended, by the view's stage (the
// window opening, open, closing), on jsbeeb's Master.
//
//   node tools/missilefps.mjs [--hold KEYS] [--frames] [--build DIR]
//
// It loads build/starglider.ssd's files where !BOOT leaves them (as
// tools/fps.mjs does), flies straight for a few seconds, presses L, and
// for each frame drawn reads the window's step (m_iris) and the cycles of
// its parts: the erase, the drawing under the objects (view_under: the
// window, the sight, the dots), the objects, and the panel (to the step's
// logic). Each stage's line: its frames, the steps they spanned, the
// fields a frame, and each part's mean and most cycles. --hold holds keys
// (jsbeeb's names, comma-separated) from the launch, --frames prints each
// frame. --build reads DIR's starglider.ssd and its symbols, not build's.
import path from "node:path";
import { pathToFileURL } from "node:url";
const root = process.cwd();
const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
const { loadDisc, toGame } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(name);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const hold = opt("--hold", "").split(",").filter(Boolean);
const build = opt("--build", "build");
const each = args.includes("--frames");
const sym = loadSymbols(path.join(root, build, "starglider.json"));
const tm = new TestMachine("Master");
await tm.initialise();
const q = console.log;
console.log = () => {};
await tm.runUntilInput();
console.log = q;
const cpu = tm.processor;
const ram = cpu.ramRomOs;                           // (ANDY is at &8000 in jsbeeb's memory)
loadDisc(tm, path.join(root, build, "starglider.ssd"), sym);
await toGame(tm, sym);
await tm.runFor(6 * 2000000);

// each frame's marks, by the routines' entries in main RAM
const marks = new Map([
    [sym.frame, "frame"],
    [sym["frame.erased"], "erased"],
    [sym.view_under, "under"],
    [sym.view_objects, "objects"],
    [sym.draw_end, "end"],
    [sym.panel_draw, "panel"],
    [sym.step_logic, "logic"],
]);
const word = (a) => ram[a] | (ram[a + 1] << 8);
let cur = null;
const frames = [];
cpu.debugInstruction.add((pc) => {
    const m = marks.get(pc);
    if (m === undefined) return false;
    const t = tm.elapsedCycles;
    if (m === "frame") {
        cur = { t: { frame: t }, steps: word(sym.steps) };
    } else if (cur && m === "logic") {
        if (cur.t.panel !== undefined) {
            cur.t.logic = t;
            cur.iris = ram[sym.m_iris];
            cur.mv = ram[sym.mv_render];
            frames.push(cur);
        }
        cur = null;
    } else if (cur && cur.t[m] === undefined) {
        cur.t[m] = t;
    }
    return false;
});
const startSteps = word(sym.steps);
tm.keyDown("KeyL");
await tm.runFor(0.3 * 2000000);
tm.keyUp("KeyL");
for (const k of hold) tm.keyDown(k);
// until the view has ended (or a minute)
for (let s = 0; s < 600; s++) {
    await tm.runFor(0.1 * 2000000);
    if (frames.length > 2 && !frames[frames.length - 1].mv && frames.some((f) => f.mv)) break;
}

const parts = (f) => ({
    erase: f.t.erased - f.t.frame,
    under: f.t.objects - f.t.under,
    objects: f.t.end - f.t.objects,
    panel: f.t.logic - f.t.panel,
    frame: f.t.logic - f.t.frame,
});
// the stage: opening (m_iris falling), open, closing (rising), after
const views = frames.filter((f) => f.mv);
const stage = (i) => {
    const f = views[i];
    if (f.iris === 0) return "open";
    const prev = views.slice(0, i).reverse().find((g) => g.iris !== f.iris);
    const next = views.slice(i + 1).find((g) => g.iris !== f.iris);
    if (prev && prev.iris < f.iris) return "closing";
    if (!prev && next && next.iris > f.iris) return "closing";
    return views.slice(0, i).some((g) => g.iris === 0) ? "closing" : "opening";
};
const groups = { opening: [], open: [], closing: [] };
views.forEach((f, i) => groups[stage(i)].push(f));
if (each)
    views.forEach((f, i) => {
        const p = parts(f);
        console.log(`step ${(f.steps - startSteps) & 0xffff} iris ${f.iris} ${stage(i)}: ` +
            Object.entries(p).map(([k, v]) => `${k} ${v}`).join(" "));
    });
for (const [name, fs] of Object.entries(groups)) {
    if (!fs.length) continue;
    const after = frames[frames.indexOf(fs[fs.length - 1]) + 1];
    const steps = ((after ?? fs[fs.length - 1]).steps - fs[0].steps) & 0xffff;
    const fields = ((after ?? fs[fs.length - 1]).t.frame - fs[0].t.frame) / 40000;
    const ps = fs.map(parts);
    const stat = (k) => {
        const xs = ps.map((p) => p[k]);
        return `${k} ${Math.round(xs.reduce((a, b) => a + b, 0) / xs.length)}/${Math.max(...xs)}`;
    };
    console.log(`${name.padEnd(8)} ${fs.length} frames over ${steps} steps, ` +
        `${(fields / fs.length).toFixed(2)} fields a frame; cycles mean/most: ` +
        ["erase", "under", "objects", "panel", "frame"].map(stat).join(", "));
}
process.exit(0);
