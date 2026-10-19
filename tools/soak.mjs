// The whole disc played for a long time, on jsbeeb's Master, by a player
// that's random but reproducible from a seed, and watched for what only
// long play finds: hangs, crashes, memory scribbled on, a bank or ACCCON
// left wrong by an interrupt, an interrupt starved, the palette split late,
// the erase leaving the view unclean, and the logic's state going where the
// ST's can't.
//
// The player flies (turning, climbing, diving, at every speed), fires,
// launches and steers missiles, steers at silos to dock (and now and then
// is put at a silo's mouth), interrogates, picks up missiles, launches; it
// enters the cheat (right and wrong, timed out), and in cheat mode freezes
// the enemies and takes points; it changes level, by points or by the
// score's level byte, dies (by the ground, by its enemies, or told to),
// presses Esc; on the title it waits out the credits, defines keys, starts
// games by any key, and in cheat mode looks at the models.
//
// What it watches, the hooks on jsbeeb's CPU:
// - every instruction: that the PC is the start of an instruction of the
//   file that's in memory there (build/starglider.lst, baron's listing, says
//   which bytes are which), or the MOS's interrupt entry; no BRK; the
//   stack's depth; and at each RTI, that the interrupt put the bank and
//   ACCCON's X, Y and E back;
// - every write: that it lands on a variable, not on code or a table, but
//   for the code each routine patches (PATCHED, below), the disc's loads,
//   and what the port keeps in its tables (KEPT); that the drawing writes the
//   screens only inside the view's window, and nothing writes main RAM's
//   cockpit out of play;
// - the fields' count and the split's time, from the interrupt's writes;
// - each step's top: the logic's state within the ST's ranges (invariants);
// - each erase: the window of the screen to be drawn empty (as
//   tools/erasecheck.mjs has it);
// - each far object's vertex taken as inside the window: that it is, and
//   how near its object's reach it comes;
// - each game's start, the player idle: after FRESH_STEPS, everything the
//   game holds as the first game held it (fresh, below);
// - the engine: fields, steps and frames moving on, and a heartbeat from
//   every waiting loop, or it's a hang.
//
//   node tools/soak.mjs [--seed N] [--secs S] [--json FILE] [--log] [--allow KINDS] [--census]
//   node tools/soak.mjs --seeds A-B [--jobs J] [--secs S] [--out DIR] [--allow KINDS] [--census]
//
// One seed plays S seconds of emulated time (the start's loads included)
// and exits 1 if it found anything but the kinds --allow names (split,
// fresh, ...), which it reports; --log prints each action as it's taken;
// --census counts every write on a file's code or data, allowed or not, by
// writer and target, for the rules below. --seeds runs a range of seeds J
// at a time, each its own process, and prints what each found. A seed and
// its seconds reproduce a run exactly: jsbeeb is deterministic, and the
// player decides only from the machine's state and its own random numbers.
// SOAK_TRACE=1 records each game's first steps' random numbers, and
// compares the lists, zero page and the workspace too.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { fork } from "node:child_process";
import os from "node:os";

const root = process.cwd();
const argv = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = argv.indexOf(`--${name}`);
    if (i < 0) return dflt;
    const v = argv[i + 1];
    argv.splice(i, 2);
    return v;
};
const flag = (name) => {
    const i = argv.indexOf(`--${name}`);
    if (i < 0) return false;
    argv.splice(i, 1);
    return true;
};
const SECS = Number(opt("secs", "300"));
const SEEDS = opt("seeds", null);
// a split late, in cycles: LATE is speechcheck's measure; a scan line later
// is a line of the panel in the view's colour
const LATE = 40, SCAN = 128;

if (SEEDS) await parent();
else await child();

// --- many seeds, a process each ----------------------------------------------
async function parent() {
    const [a, b = a] = SEEDS.split("-").map(Number);
    const jobs = Number(opt("jobs", String(Math.max(1, Math.min(12, os.cpus().length >> 1)))));
    const out = opt("out", "build/soak");
    const passed = ["census"].filter(flag).map((f) => `--${f}`);
    const allow = opt("allow", null);
    if (allow) passed.push("--allow", allow);
    fs.mkdirSync(out, { recursive: true });
    const seeds = [];
    for (let s = a; s <= b; s++) seeds.push(s);
    const results = [];
    const t0 = Date.now();
    const run = (seed) =>
        new Promise((resolve) => {
            const json = path.join(out, `seed${seed}.json`);
            const p = fork(path.join(root, "tools/soak.mjs"), ["--seed", String(seed), "--secs", String(SECS), "--json", json, ...passed], {
                silent: true,
            });
            let text = "";
            p.stdout.on("data", (d) => (text += d));
            p.stderr.on("data", (d) => (text += d));
            p.on("exit", (code) => {
                let r = null;
                try {
                    r = JSON.parse(fs.readFileSync(json, "utf8"));
                } catch {}
                results.push({ seed, code, r, text });
                const line = r ? summary(r) : `seed ${seed}: no result (exit ${code})\n${text}`;
                console.log(line);
                resolve();
            });
        });
    const queue = [...seeds];
    await Promise.all(
        Array.from({ length: Math.min(jobs, queue.length) }, async () => {
            while (queue.length) await run(queue.shift());
        }),
    );
    const bad = results.filter((x) => x.code !== 0);
    const emu = results.reduce((s, x) => s + (x.r ? x.r.secs : 0), 0);
    console.log(spread(results.filter((x) => x.r).map((x) => x.r.splits)));
    console.log(`soak: ${results.length} seeds, ${(emu / 60).toFixed(1)} minutes emulated in ${((Date.now() - t0) / 60000).toFixed(1)} minutes; ` +
        `${bad.length} found something`);
    process.exit(bad.length ? 1 : 0);
}

// the splits' spread over every seed, by what was going on: how many came
// more than LATE (speechcheck's late) and more than a scan line after each
// seed's earliest, the worst beyond the disc's NMIs, and the worst of the
// sync's interrupt then; and apart, those the NMIs held so late
function spread(all) {
    const by = {};
    const KEYS = ["n", "late", "line", "held", "heldLine"], WORST = ["worst", "worstHeld", "worstSync"];
    for (const s of all)
        for (const [ctx, b] of Object.entries(s.by)) {
            const t = (by[ctx] ??= Object.fromEntries([...KEYS, ...WORST].map((k) => [k, 0])));
            for (const k of KEYS) t[k] += b[k] ?? 0;
            for (const k of WORST) t[k] = Math.max(t[k], b[k] ?? 0);
        }
    const sum = (k) => Object.values(by).reduce((s, b) => s + b[k], 0);
    const most = (k) => Math.max(0, ...Object.values(by).map((b) => b[k])) / 2;
    const pc = (a, n) => `${((100 * a) / Math.max(1, n)).toFixed(2)}%`;
    const n = sum("n");
    return [`splits: ${n}, ${pc(sum("late"), n)} more than ${LATE / 2}us after the earliest, ${pc(sum("line"), n)} more than a scan line, ` +
        `the worst ${most("worst")}us beyond the disc's NMIs; held by them, ${pc(sum("held"), n)} more than ${LATE / 2}us, ` +
        `${pc(sum("heldLine"), n)} a line, the worst ${most("worstHeld")}us`,
        ...Object.entries(by).sort(([, a], [, b]) => b.n - a.n).map(([ctx, b]) =>
            `  ${ctx}: ${b.n}, ${pc(b.late, b.n)} late, ${pc(b.line, b.n)} a line, the worst ${b.worst / 2}us beyond the NMIs; ` +
            `held ${pc(b.held, b.n)}, ${pc(b.heldLine, b.n)} a line, the worst ${b.worstHeld / 2}us (the sync's interrupt ${b.worstSync / 2}us)`)].join("\n");
}

// a seed's line, its problems', and a line for each allowed kind's
function summary(r) {
    const head = `seed ${r.seed}: ${r.secs.toFixed(0)}s, ${r.steps} steps, ${r.frames} frames, ${r.games} games, ` +
        `levels to ${r.maxLevel}, ${r.dockings} dockings, ${r.missiles} missiles, deepest stack &${r.minS.toString(16)}, ` +
        `splits ${r.splits.n} (${r.splits.late} late, the worst by ${r.splits.worst} cycles beyond the disc's NMIs; ` +
        `${r.splits.held ?? 0} held by them, the worst by ${r.splits.worstHeld ?? 0}), worst field ${r.worstField}, ` +
        `a vertex past its reach by ${r.reachPast}; ` +
        Object.entries(r.entered ?? {}).map(([p, n]) => `${p} ${n}`).join(", ");
    const allowed = new Set(r.allow ?? []);
    const lines = r.problems.filter((p) => !allowed.has(p.kind))
        .map((p) => `  ${p.kind} x${p.count} at ${p.at.toFixed(2)}s (step ${p.step}, ${p.phase}): ${p.what}`);
    for (const kind of allowed) {
        const ps = r.problems.filter((p) => p.kind === kind);
        if (ps.length) lines.push(`  (${kind}, allowed: ${ps.length} kinds, ${ps.reduce((s, p) => s + p.count, 0)} times, the first at ${ps[0].at.toFixed(2)}s)`);
    }
    return [head, ...lines].join("\n");
}

// --- one seed --------------------------------------------------------------
async function child() {
    const SEED = Number(opt("seed", "1"));
    const JSON_OUT = opt("json", null);
    const LOG = flag("log");
    const CENSUS = flag("census");             // every write on a file's code or data, allowed or not, counted
    const ALLOW = new Set(opt("allow", "").split(",").filter(Boolean));   // kinds of problem reported, not failed on
    const census = new Map();
    const { loadSymbols } = await import(pathToFileURL(path.join(root, "tools/beeb.mjs")).href);
    const { loadDisc, ssdFiles, fieldCycles } = await import(pathToFileURL(path.join(root, "tools/disc.mjs")).href);
    const { TestMachine } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/test-machine.js")).href);
    const disc = path.join(root, "build/starglider.ssd");
    const sym = loadSymbols(path.join(root, "build/starglider.json"));
    const files = ssdFiles(disc);
    const panel = JSON.parse(fs.readFileSync(path.join(root, "build/gen/panel.json"), "utf8"));
    const winRaw = fs.readFileSync(path.join(root, "build/gen/window.raw"));

    const tm = new TestMachine("Master");
    await tm.initialise();
    const q = console.log;
    console.log = () => {};
    await tm.runUntilInput();
    console.log = q;
    const cpu = tm.processor;
    const ram = cpu.ramRomOs;
    const CYCLES = 2000000;
    const FIELD = fieldCycles(sym);                     // (the TestMachine's, which loadDisc sets)
    const SHADOW = 0x8000;                              // (jsbeeb's array keeps shadow RAM there on)
    const now = () => cpu.cycleSeconds * CYCLES + cpu.currentCycles;
    const secs = () => now() / CYCLES;
    const word = (a) => ram[a] | (ram[a + 1] << 8);
    const s16 = (a) => (word(a) << 16) >> 16;

    // --- the player's random numbers (mulberry32) ---
    let rs = SEED >>> 0;
    const rand = () => {
        rs = (rs + 0x6d2b79f5) >>> 0;
        let t = rs;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    const chance = (p) => rand() < p;
    const between = (a, b) => a + Math.floor(rand() * (b - a + 1));
    const pick = (list) => list[Math.floor(rand() * list.length)];
    const weighted = (pairs) => {
        const total = pairs.reduce((s, [w]) => s + w, 0);
        let r = rand() * total;
        for (const [w, v] of pairs) if ((r -= w) < 0) return v;
        return pairs[pairs.length - 1][1];
    };

    // --- the listing: which bytes of each file are code, data and variables ---
    // each section's place, and its labels by address (baron's symbols): a
    // routine's (top-level) and those in its scope (routine.label), macros'
    // own left out
    const sizes = {}, secLabels = {};
    for (const sec of JSON.parse(fs.readFileSync(path.join(root, "build/starglider.json"), "utf8")).assemblies[0].sections) {
        if (!sec.name) continue;
        if (sec.attributes?.org !== undefined) sizes[sec.name] = { org: sec.attributes.org, size: sec.size };
        secLabels[sec.name] = Object.entries(sec.labels ?? {})
            .filter(([k]) => !k.includes("@"))
            .map(([name, v]) => ({ addr: v.value, name, top: !name.includes(".") }))
            .sort((a, b) => a.addr - b.addr || a.top - b.top);
    }
    const listing = parseListing(fs.readFileSync(path.join(root, "build/starglider.lst"), "utf8"), sizes);
    // where each section's file lies: the file, its address at the file's
    // start, and its place in jsbeeb's memory (HAZEL at &9000, the banks
    // past romOffset)
    const bankAt = (b) => (a) => cpu.romOffset + b * 16384 + (a - 0x8000);
    const PLACES = {
        Main: { file: "SG", from: 0x0e00, phys: (a) => a },
        Nmi: { file: "SG", from: 0x0d00 - (sym.nmi_load - 0x0e00), phys: (a) => a },
        Tables: { file: "TABLES", from: 0xc000, phys: (a) => 0x9000 + (a - 0xc000) },
        Code2: { file: "CODE2", from: 0xd000, phys: (a) => 0x9000 + (a - 0xc000) },
        Shapes: { file: "SHAPES", from: 0x8000, phys: bankAt(sym.BANK_SHAPES) },
        WorldBank: { file: "WORLD", from: 0x8000, phys: bankAt(sym.BANK_WORLD) },
        LogicBank: { file: "LOGIC", from: 0x8000, phys: bankAt(sym.BANK_LOGIC) },
        SpeechA: { file: "SPEECH", from: 0x8000, phys: bankAt(sym.BANK_PIC) },
        WindowPic: { file: "WINDOW", from: 0x9000, phys: bankAt(sym.BANK_PIC) },
        Docked: { file: "DOCKED", from: 0x9000, phys: bankAt(sym.BANK_PIC) },
        Front: { file: "FRONT", from: 0x8000, phys: bankAt(sym.BANK_PIC) },
    };
    const DF = ["SHAPES", "WORLD", "TABLES", "CODE2", "COCKPIT", "LOGIC", "WINDOW", "SPEECH", "FRONT", "DOCKED"];
    DF.forEach((f, i) => {
        if (sym[`DF_${f}`] !== i) throw new Error(`DF_${f} isn't ${i}`);
    });
    const NONE = 0, OP = 1, ARG = 2, DATA = 3, VAR = 4;
    // The code each routine patches: the routine (its top-level label in
    // baron's symbols), and the file and routine of what it patches; and the
    // variables a file keeps in its own bytes (EQUBs, so that a load
    // starts them), by file and label. Every other write on a file's code
    // or data is a problem. (The NMI routine's writes are the disc's loads,
    // and its own counts.)
    const PATCHED = [
        [/^w_start$/, /^SG:nmi_(bank|dst)$/],
        [/^(speech_begin|sp_\w+)$/, /^SG:sp_(at|bank|next|due_lo|due_hi)$/],
        [/^clip_window$/, /^(SG:(clip_line|far_place|vertex|vertex_far)|WINDOW:box_end)$/],
        [/^rotate_setup$/, /^WORLD:(rot\d_\w+|rap\d_\w+|rap_\w+|rot_\w+|rotc\d_go|rapc\d_go|rotate_exact)$/],
        [/^rotate_lists$/, /^WORLD:rotate_lists$/],
        [/^ground_setup$/, /^WINDOW:(gk\d|gt\d_\w+|ground_all)$/],
        [/^screen_setup$/, /^(CODE2:(s8\d_\w+|sc\d_\w+)|SG:vertex_far)$/],
        [/^xform_setup$/, /^CODE2:(xf\d_\w+|xfrow\d_k|xform_back)$/],
        [/^set_colour$/, /^CODE2:(set_colour|s[lr]_s\d|t[lr]_s\dx)$/],
        [/^line_mode$/, /^CODE2:(s[lr]_w[0-3b]|t[lr]_w[0-3]|tv_w)$/],
        [/^shallow_[lr]$/, /^CODE2:s[lr]_sbc\d$/],
        [/^steep_[lr]$/, /^CODE2:t[lr]_t\d$/],
        [/^line_(draw|erase)$/, /^CODE2:(sr_single|tv_next)$/],
        [/^tr_single$/, /^CODE2:tv_m$/],
        [/^erase_aim$/, /^CODE2:line_plot$/],
        [/^erase_box$/, /^WINDOW:erase_box$/],
        [/^erase_screen$/, /^TABLES:erase_screen$/],
        [/^screen_clear$/, /^TABLES:screen_clear$/],
        [/^faces$/, /^SG:faces$/],
        [/^far_recip$/, /^WINDOW:far_pv$/],
        [/^(far_setup|proj_z)$/, /^SG:proj_x$/],
        [/^draw_shape$/, /^(CODE2:xform_back|SG:(draw_shape|edges|vertex))$/],
        [/^edges_far$/, /^SG:edges_far$/],
        [/^box_aim$/, /^WINDOW:box_log$/],
        [/^flash_part$/, /^WINDOW:flash_part$/],
        [/^dots_draw$/, /^WINDOW:dot_[xy]$/],
    ];
    const KEPT = new RegExp("^(" + [
        "WORLD:(cam_valid|dot_made|dot_mv_was|dot_valid|rap_sm8_lo|rap_sm8_hi|rot_ke_lo|rot_ke_hi|rot_exactly|rot_identity|rot_shape|rot_was|rotate_setup\\.\\w+)",
        "WINDOW:(dv_some|dv_gen|dv_mv|gy_was)",
        "SG:(gm_n|gm_next|gm_pitch|gm_roll|om_n|om_next|key_defined)",
        "FRONT:(fe_st_colour|fe_state)",
    ].join("|") + ")$");
    const images = [];
    for (const sec of listing) {
        const place = PLACES[sec.name];
        if (!place) continue;
        const file = files[place.file];
        const lo = Math.min(...sec.items.map((it) => it.addr), ...sec.labels.map((l) => l.addr));
        const hi = Math.max(...sec.items.map((it) => it.addr + it.len));
        const img = { name: sec.name, file: place.file, org: lo, size: hi - lo, phys0: place.phys(lo), kind: new Uint8Array(hi - lo).fill(DATA) };
        img.bytes = file.subarray(lo - place.from, hi - place.from);
        for (const it of sec.items) {
            const off = it.addr - img.org;
            for (let i = 0; i < it.len; i++) img.kind[off + i] = it.kind === OP ? (i ? ARG : OP) : it.kind;
            if (it.kind === VAR) continue;
            it.bytes.forEach((b, i) => {
                if (img.bytes[off + i] !== b)
                    throw new Error(`build/starglider.lst isn't the disc's: ${sec.name} &${(it.addr + i).toString(16)} is &${b.toString(16)} in it, ` +
                        `&${img.bytes[off + i].toString(16)} in ${place.file} (make build/starglider.lst)`);
            });
        }
        img.labels = secLabels[sec.name] ?? [];
        img.tops = img.labels.filter((l) => l.top);
        images.push(img);
    }
    const imageNamed = Object.fromEntries(images.map((img) => [img.name, img]));
    // a byte's name: the last label at or before it, and the last routine's
    const lastAt = (list, a) => {
        let lo = 0, hi = list.length - 1, best = -1;
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            if (list[mid].addr <= a) {
                best = mid;
                lo = mid + 1;
            } else hi = mid - 1;
        }
        return best < 0 ? null : list[best];
    };
    function labelOf(img, off) {
        const a = img.org + off;
        const l = lastAt(img.labels, a);
        if (!l) return `${img.name}+&${off.toString(16)}`;
        return a === l.addr ? l.name : `${l.name}+${a - l.addr}`;
    }
    function routineOf(img, off) {
        const l = lastAt(img.tops, img.org + off);
        return l ? l.name : img.name;
    }

    // which image owns each byte of jsbeeb's memory: the resident ones once
    // loaded; bank 7's as each load lands (the NMI routine's writes)
    const owner = new Int8Array(ram.length);
    const patched = new Uint8Array(ram.length);         // opcodes written since their load
    const own = (img) => {
        for (let i = 0; i < img.size; i++) owner[img.phys0 + i] = images.indexOf(img) + 1;
    };
    const imageAt = (phys) => (owner[phys] ? images[owner[phys] - 1] : null);
    function where(phys) {
        const img = imageAt(phys);
        if (img) return labelOf(img, phys - img.phys0);
        if (phys >= cpu.osOffset) return `MOS &${(0xc000 + phys - cpu.osOffset).toString(16)}`;
        return `&${phys.toString(16)}`;
    }

    // --- the labels the hooks fire on (by image, so bank 7's are its own) ---
    const marks = new Int16Array(ram.length);
    const markList = [null];
    const markImage = [null];
    function mark(name, imgName, fn, plus = 0) {
        const a = sym[name];
        if (a === undefined) throw new Error(`no symbol ${name}`);
        const phys = PLACES[imgName].phys(a + plus);
        if (marks[phys]) throw new Error(`${name} is at ${markList[marks[phys]].name}'s address`);
        markList.push({ name, fn });
        markImage.push(imageNamed[imgName]);
        marks[phys] = markList.length - 1;
    }

    // --- what's found ---
    const problems = new Map();
    let fatal = null;
    const recent = [];                                  // the player's last actions
    let phase = "boot";
    let armed = false;
    const steps = () => word(sym.steps);
    function problem(kind, key, what, { stop = false, detail = null } = {}) {
        const k = `${kind}:${key}`;
        const p = problems.get(k);
        if (p) {
            p.count++;
            return;
        }
        const entry = { kind, what, count: 1, at: secs(), step: steps(), phase, pc: where(physPc(cpu.pc)), detail, recent: recent.slice(-12) };
        if (stop) entry.history = history();
        problems.set(k, entry);
        if (LOG) console.log(`PROBLEM ${kind} at ${entry.at.toFixed(2)}s: ${what}`);
        if (stop && !fatal) {
            fatal = entry;
            cpu.stop();
        }
    }
    const physPc = (pc) => {
        const so = cpu.memStatOffsetByIFetchBank & (1 << (pc >>> 12)) ? 256 : 0;
        return cpu.memLook[so + (pc >>> 8)] + pc;
    };
    // the last instructions, by name (jsbeeb keeps their PCs)
    function history() {
        const out = [];
        for (let i = 31; i >= 0; i--) out.push(`&${cpu.getPrevPc(i).toString(16)}`);
        return { pcs: out.join(" "), a: cpu.a, x: cpu.x, y: cpu.y, s: cpu.s, romsel: cpu.romsel, acccon: cpu.acccon };
    }

    // --- the hooks ---
    let minS = 0xff, minSAt = 0;
    let mosEntry = null;                                // the MOS's IRQ entry: from its vector to JMP (IRQ1V)
    const intStack = [];
    const loopS = new Map();
    let lastBeat = 0;
    cpu.debugInstruction.add((pc, op) => {
        const so = cpu.memStatOffset + (pc >>> 8);
        const phys = cpu.memLook[so] + pc;
        const m = marks[phys];
        if (m && (!armed || imageAt(phys) === markImage[m])) markList[m].fn(phys);
        if (!armed) return false;
        if (cpu.s < minS) {
            minS = cpu.s;
            minSAt = phys;
        }
        if (cpu.memStat[so] === 0) {
            problem("pc", "device", `the PC at &${pc.toString(16)}, the devices' page`, { stop: true });
            return true;
        }
        const o = owner[phys];
        if (o) {
            const img = images[o - 1];
            const off = phys - img.phys0;
            if (img.kind[off] !== OP || (img.bytes[off] !== op && !patched[phys])) {
                problem("pc", `${phys}`, `the PC at &${pc.toString(16)} (${where(phys)}), not an instruction of ${img.file}'s: ` +
                    `&${op.toString(16)} there`, { stop: true });
                return true;
            }
        } else if (phys >= cpu.osOffset && phys < cpu.osOffset + 16384) {
            if (!mosEntry.has(pc)) {
                problem("pc", `mos${pc}`, `the PC at &${pc.toString(16)} in the MOS, outside its interrupt entry`, { stop: true });
                return true;
            }
        } else {
            problem("pc", `${phys}`, `the PC at &${pc.toString(16)} (${where(phys)}), in no file's code`, { stop: true });
            return true;
        }
        if (op === 0x40 && intStack.length && cpu.s === intStack[intStack.length - 1].s - 3) {
            const e = intStack.pop();
            if (e.vector === NMI0) {
                nmis.push([e.at, now() + 6]);           // (with the RTI's own six cycles)
                if (nmis.length > 8) nmis.shift();
            }
            if (cpu.romsel !== e.romsel && cpu.romsel !== e.bankNow)
                problem("interrupt", `romsel${e.vector}`, `an interrupt (to &${e.vector.toString(16)}) returned with ROMSEL &${cpu.romsel.toString(16)}, ` +
                    `taken with &${e.romsel.toString(16)} (bank_now &${e.bankNow.toString(16)})`);
            if ((cpu.acccon & 0x0e) !== (e.acccon & 0x0e))
                problem("interrupt", `acccon${e.vector}`, `an interrupt (to &${e.vector.toString(16)}) returned with ACCCON &${cpu.acccon.toString(16)}, ` +
                    `taken with &${e.acccon.toString(16)}`);
        }
        return false;
    });
    const brk = cpu.brk;
    cpu.brk = function (isIrq) {
        if (!isIrq) {
            if (armed) problem("brk", `${this.pc}`, `BRK at &${((this.pc - 1) & 0xffff).toString(16)} (${where(physPc((this.pc - 1) & 0xffff))})`, { stop: true });
            return brk.call(this, isIrq);
        }
        const e = { s: this.s, romsel: this.romsel, acccon: this.acccon, bankNow: ram[sym.bank_now], vector: 0, at: now() };
        brk.call(this, isIrq);
        e.vector = this.pc;
        intStack.push(e);
        if (intStack.length > 8) intStack.shift();
    };

    // the writes
    const screenOut = new Map();                        // writers outside the window, by screen and phase
    const lastWriter = new Int32Array(0x10000 - sym.SCREEN);  // each screen byte's last writer
    const SCREEN = sym.SCREEN;
    const WIN_X0 = sym.WINDOW_COL0, WIN_X1 = sym.WINDOW_COL0 + sym.WINDOW_COLS;
    let loading = null;                                 // the image the disc's NMI routine is filling
    let lastField = 0, worstField = 0;
    // The palette split must land in the horizontal blank between the view's
    // last line and the panel's first (engine.6502), a fixed time from the
    // vertical sync's start, which jsbeeb's TestMachine keeps (it has no
    // CRTC: its field is a count of cycles, the CRTC's: tools/disc.mjs).
    // Each split's last write by the split's own code (irq_handler's: not
    // the level flash's strobe, nor its put-back below the split) is timed
    // from the sync, and how much later than the earliest is counted by
    // what else was going on: a read's NMIs, speech, an effect's ticks, a
    // key held (the vertical sync's longest work). The sync's interrupt is
    // timed too, by its count of the field, which the split no longer waits
    // on. The disc's NMIs, which nothing holds off, are timed from their
    // entry to their RTI: a split no later than LATE beyond the time they
    // took since its earliest moment is theirs, and counted apart (held);
    // one later than that is a problem. (LATE and SCAN, above.)
    const SPLIT0 = sym.irq_handler, SPLIT1 = sym["irq_handler.not_split"];
    const nmis = [];
    const nmiTime = (from, to) => nmis.reduce((t, [a, b]) => t + Math.max(0, Math.min(b, to) - Math.max(a, from)), 0);
    let splitN = 0, vsyncAt = 0, syncNow = 0;
    const setVBlankInt = cpu.sysvia.setVBlankInt;
    cpu.sysvia.setVBlankInt = function (level) {
        if (level) vsyncAt = now();
        return setVBlankInt.call(this, level);
    };
    const splits = { n: 0, least: Infinity, leastSync: Infinity, by: {} };
    const context = () => ["disc", "speech", "effect", "key"].filter((_, i) =>
        [ram[sym.fdc_state], word(sym.sample_left) | word(sym.sample_left + 2), ram[sym.ta_kind], ram[sym.keys_held]][i]).join("+") || "none";
    function syncLate(v) {
        splits.leastSync = Math.min(splits.leastSync, v);
        syncNow = v - splits.leastSync;
    }
    function splitAt(d) {
        const ctx = context();
        const b = (splits.by[ctx] ??= { n: 0, late: 0, line: 0, held: 0, heldLine: 0, worst: 0, worstHeld: 0, worstSync: 0 });
        splits.n++;
        b.n++;
        splits.least = Math.min(splits.least, d);
        if (splits.n < 100) return;
        const late = d - splits.least;
        // (from the earliest less a line: the interrupt's way to the split)
        const own = late - nmiTime(vsyncAt + splits.least - SCAN, now());
        b.worstSync = Math.max(b.worstSync, syncNow);
        b.worst = Math.max(b.worst, own);
        if (late > LATE && own <= LATE) {
            b.held++;
            if (late > SCAN) b.heldLine++;
            b.worstHeld = Math.max(b.worstHeld, late);
            return;
        }
        if (late <= LATE) return;
        b.late++;
        if (late > SCAN) b.line++;
        problem("split", `late:${ctx}`, `the palette split ${late} cycles after its earliest from the vertical sync, ` +
            `${own} beyond the disc's NMIs (${ctx}; the sync's interrupt ${syncNow} after its earliest)`, { detail: { split: pcRoutines() } });
    }
    // the last instructions run, by routine, the latest last
    function pcRoutines() {
        const out = [];
        for (let i = 255; i >= 0; i--) {
            const pc = cpu.getPrevPc(i);
            const r = writerRoutine(physPc(pc));
            if (out.length && out[out.length - 1][0] === r) out[out.length - 1][1]++;
            else out.push([r, 1]);
        }
        return out.map(([r, n]) => `${r}x${n}`).join(" ");
    }
    const NMI0 = 0x0d00, NMI1 = sym.NMI_PAGE + 0x40;
    cpu.debugWrite.add((addr, val) => {
        if (addr >= 0xfc00 && addr < 0xff00) {
            if (addr === 0xfe21) {
                // the split's four writes: when the last lands, from the
                // sync's start
                const pc = cpu.oldPcArray[cpu.oldPcIndex];
                if (pc < SPLIT0 || pc >= SPLIT1) splitN = 0;
                else if (++splitN === 4) {
                    if (phase === "play") splitAt(now() - vsyncAt);
                    splitN = 0;
                }
            }
            return;
        }
        const so = cpu.memStatOffset + (addr >>> 8);
        if (cpu.memStat[so] !== 1) return;
        const phys = cpu.memLook[so] + addr;
        if (phys === sym.fields) {
            const t = now();
            if (phase === "play" && armed) syncLate(t - vsyncAt);
            if (lastField && armed) {
                const gap = t - lastField;
                if (Math.abs(gap - FIELD) > Math.abs(worstField)) worstField = gap - FIELD;
                if (gap > 1.5 * FIELD) problem("field", "late", `a vertical sync's interrupt ${(gap / FIELD).toFixed(2)} fields after the last`);
            }
            lastField = t;
            return;
        }
        const wpc = cpu.oldPcArray[cpu.oldPcIndex];
        const wphys = cpu.memLook[cpu.memStatOffset + (wpc >>> 8)] + wpc;
        if (wphys >= NMI0 && wphys < NMI1) {
            // a byte of a load: bank 7's is the loading file's from now on
            if (loading && phys >= loading.phys0 && phys < loading.phys0 + loading.size) owner[phys] = images.indexOf(loading) + 1;
            patched[phys] = 0;
            return;
        }
        if (!armed) return;
        // the screens: main RAM's from SCREEN, shadow's at SHADOW on
        const scr = phys >= SCREEN && phys < 0x8000 ? 0 : phys >= SHADOW + SCREEN && phys < 0x10000 ? 1 : -1;
        if (scr >= 0) {
            lastWriter[phys - SCREEN] = wphys;
            const off = (phys & 0x7fff) - SCREEN;
            const y = ((off / 640) | 0) * 8 + (off & 7), col = (off % 640) >> 3;
            if (y < sym.VIEW_YMIN || y > sym.VIEW_YMAX || col < WIN_X0 || col >= WIN_X1) {
                const routine = writerRoutine(wphys);
                const key = `${scr}:${phase}:${routine}`;
                screenOut.set(key, (screenOut.get(key) ?? 0) + 1);
                if (!screenAllowed(scr, imageAt(wphys), routine, y, col) && ram[phys] !== val)
                    problem("screen", `${key}:${y}`, `${where(wphys)} wrote &${val.toString(16)} over &${ram[phys].toString(16)} on the ${scr ? "shadow" : "main RAM's"} screen outside the window, at (${4 * col}, ${y}), in ${phase}`,
                        { detail: { ...drawing(), routines: pcRoutines() } });
            }
            return;
        }
        const o = owner[phys];
        if (!o) return;
        const img = images[o - 1];
        const off = phys - img.phys0;
        const k = img.kind[off];
        if (k === VAR) return;
        if (k === OP) patched[phys] = 1;
        const wimg = imageAt(wphys);
        if (CENSUS) {
            const c = `${writerRoutine(wphys)} -> ${img.file}:${routineOf(img, off)} [${["none", "op", "arg", "data"][k]}]`;
            census.set(c, (census.get(c) ?? 0) + 1);
        }
        if (allowed(img, off, k, wimg, wphys)) return;
        const target = labelOf(img, off);
        const writer = wimg ? labelOf(wimg, wphys - wimg.phys0) : where(wphys);
        problem("write", `${img.name}:${target}<-${writer}`, `${writer} wrote &${val.toString(16)} on ` +
            `${["none", "an opcode", "an operand", "data"][k]} of ${img.file}'s, ${target}`,
            { detail: { writer: writerRoutine(wphys), target: `${img.file}:${routineOf(img, off)}`, kind: k } });
    });
    // the object being drawn, for a write outside the window: its slot and
    // type, a far object's centre and reach, and its vertices this frame
    function drawing() {
        const verts = [];
        for (let v = 0; v < 128; v++)
            if (ram[sym.vert_mark + v] === ram[sym.stamp])
                verts.push([v, (((ram[sym.v_sxhi + v] << 8) | ram[sym.v_sxlo + v]) << 16) >> 16, ram[sym.v_sylo + v], ram[sym.v_code + v]]);
        return { slot: ram[sym.slot], otype: ram[sym.otype], type: ram[sym.ob_type + ram[sym.slot]], mv: ram[sym.mv_render],
            centre: [s16(sym.sc_0), s16(sym.sc_0 + 2)], quarters: [s16(sym.sc_0q), s16(sym.sc_0q + 2)], far_inside: ram[sym.far_inside],
            pq: word(sym.pq), radius: word(sym.sh_radius), tz: word(sym.tz), line: [s16(sym.cx0), s16(sym.cy0), s16(sym.cx1), s16(sym.cy1)], verts };
    }
    const routines = new Map();
    function writerRoutine(wphys) {
        let r = routines.get(wphys);
        if (r === undefined) {
            const wimg = imageAt(wphys);
            r = wimg ? routineOf(wimg, wphys - wimg.phys0) : where(wphys);
            routines.set(wphys, r);
        }
        return r;
    }
    // Outside the view's window: in play, the panel's (the logic bank's)
    // and the cockpit's copy into the shadow screen; out of play the front
    // end's, on the shadow screen, which it shows, and G's viewer's clear of
    // both. Main RAM's screen keeps the cockpit for the next game.
    const PLAYING = new Set(["play", "prompt", "interrogate", "ending", "loading"]);
    // (and the missile view's window, which is the picture's rows 10-130:
    // its first character row's lines above it put back as it's drawn)
    const MVIEW = new Set(["cells_copy", "cells_zero", "lines_01", "lines_02", "lines_02_zero"]);
    function screenAllowed(scr, wimg, routine, y, col) {
        if (wimg && wimg.name === "LogicBank") return true;
        if (MVIEW.has(routine) && y >= 8 && y <= 130 && col >= WIN_X0 && col < WIN_X1) return true;
        if (scr === 1 && (routine === "screen_copy" || !PLAYING.has(phase))) return true;
        return phase === "viewer" && routine === "screen_clear";
    }
    // the code and the tables each routine may write: what it patches, and
    // what the port keeps in an initialised table
    const decided = new Map();
    function allowed(img, off, k, wimg, wphys) {
        const key = wphys * 8388608 + img.phys0 + off;
        let ok = decided.get(key);
        if (ok === undefined) {
            const target = `${img.file}:${routineOf(img, off)}`;
            const writer = wimg ? routineOf(wimg, wphys - wimg.phys0) : "";
            ok = k === DATA
                ? KEPT.test(`${img.file}:${labelOf(img, off).replace(/\+\d+$/, "")}`)
                : PATCHED.some(([w, t]) => w.test(writer) && t.test(target));
            decided.set(key, ok);
        }
        return ok;
    }

    // --- the marks ---
    const entered = {};
    const markPhase = (p) => () => {
        if (phase !== p) entered[p] = (entered[p] ?? 0) + 1;
        phase = p;
    };
    mark("front_title", "Front", () => {
        markPhase("title")();
        if (!armed) arm();
    });
    mark("front_title.poll", "Front", (phys) => loopStack("front_title.poll", 0));
    mark("fe_keys", "Front", markPhase("kscreen"));
    mark("fe_viewer", "Front", markPhase("viewer"));
    mark("front_game_over", "Front", markPhase("over"));
    mark("fe_rating", "Front", markPhase("rating"));
    mark("fe_high_score", "Front", markPhase("hiscore"));
    mark("fe_name", "Front", markPhase("name"));
    mark("fe_end_wait", "Front", markPhase("endscreen"));
    mark("fe_field", "Front", beat);
    mark("game_start", "Main", markPhase("loading"));
    mark("game_end", "Main", markPhase("ending"));
    mark("to_title", "Main", markPhase("leaving"));
    mark("play", "Main", () => {
        games++;
        // what the ST's games carry from one to the next, the first game's
        // at each start
        if (!carried) carried = CARRIED.map(([v, n]) => ram.slice(sym[v], sym[v] + n));
        else CARRIED.forEach(([v], i) => ram.set(carried[i], sym[v]));
        pendingPokes = [];                              // (the last game's player's, unmade)
        gameSteps = 0;
        framesAtPlay = word(sym.frames);
    });
    mark("engine_run.wait", "Main", () => {
        if (phase !== "play") markPhase("play")();
        loopStack("engine_run.wait", 0);
    });
    mark("wait_key", "Main", markPhase("prompt"));
    mark("wait_key_timeout", "Main", markPhase("prompt"));
    mark("interrogate", "Main", markPhase("interrogate"));
    mark("int_key", "Main", beat);
    mark("disc_step", "Main", beat);
    mark("step_lists", "Main", () => {
        beat();
        stepTop();
    });
    mark("frame.erased", "Main", erased);
    if (process.env.SOAK_TRACE)
        mark("ground_dots.ended", "WorldBank", () => {
            if (gameSteps < 0 || gameSteps > 2) return;
            const dots = [];
            for (let i = 0; i < 40; i++)
                dots.push(`${i}:${ram[sym.dot_seen + i].toString(16)}@${((ram[sym.dot_x_hi + i] << 8) | ram[sym.dot_x_lo + i]).toString(16)},` +
                    `${((ram[sym.dot_z_hi + i] << 8) | ram[sym.dot_z_lo + i]).toString(16)}`);
            (rtrace[`dots${games}`] ??= []).push(`${gameSteps} ${dots.join(" ")}`);
        });
    if (process.env.SOAK_TRACE)
        for (const r of ["random8", "random32"])
            mark(r, "Main", () => {
                if (gameSteps < 0 || gameSteps > 1) return;
                const ret = (ram[0x101 + cpu.s] | (ram[0x102 + cpu.s] << 8)) - 2;
                (rtrace[games] ??= []).push(`${gameSteps} ${r} d0 ${word(sym.rng_d0).toString(16)} mx ${s16(sym.mouse_x)} ` +
                    `lag ${[...ram.slice(sym.rng_lag, sym.rng_lag + 6)].map((b) => b.toString(16)).join(",")} from ${where(physPc(ret))}`);
            });
    // a far object's vertex taken as inside the window (far_place's reach
    // said the whole object is, or its outcode): it must be; and how far
    // past its object's reach, which bounds every vertex, it lies (the
    // reach's box, from the view's centre, as far_place leaves it)
    let reachBox = null, reachPast = -Infinity;
    mark("far_place.cut", "Main", () => {
        reachBox = ["xlo", "xhi", "ylo", "yhi"].map((k) => s16(sym[`far_place.${k}`]));
    });
    mark("vertex_far.inside", "Main", () => {
        if (!armed) return;
        const v = cpu.y;
        const x = (((ram[sym.v_sxhi + v] << 8) | ram[sym.v_sxlo + v]) << 16) >> 16;
        const y = (((ram[sym.v_syhi + v] << 8) | ram[sym.v_sylo + v]) << 16) >> 16;
        if (ram[sym.far_inside] && reachBox) {
            const [xl, xh, yl, yh] = reachBox, rx = x - sym.VIEW_CX, ry = y - sym.VIEW_CY;
            reachPast = Math.max(reachPast, rx - xh, xl - rx, ry - yh, yl - ry);
        }
        const [x0, x1, y0, y1] = ram[sym.mv_render] ? [sym.MV_XMIN, sym.MV_XMAX, sym.MV_YMIN, sym.MV_YMAX] : [sym.VIEW_XMIN, sym.VIEW_XMAX, sym.VIEW_YMIN, sym.VIEW_YMAX];
        if (x < x0 || x > x1 || y < y0 || y > y1)
            problem("reach", ram[sym.far_inside] ? "far_inside" : "outcode", `slot ${ram[sym.slot]} (type ${ram[sym.ob_type + ram[sym.slot]]}): ` +
                `its vertex ${v} at (${x}, ${y}) taken as inside the window${ram[sym.far_inside] ? " by its reach" : ""}`, { detail: drawing() });
    });
    mark("disc_load", "Main", () => loadBegun());
    mark("disc_load_first", "Main", () => loadBegun());
    mark("moving", "WindowPic", windowDrawn, 3);         // (under_draw's JMP dots_draw: the window drawn)
    function beat() {
        lastBeat = now();
    }
    function loopStack(name) {
        const s = cpu.s;
        const was = loopS.get(name);
        if (was === undefined) loopS.set(name, s);
        else if (was !== s) problem("stack", name, `the stack at &1${s.toString(16)} in ${name}'s loop, &1${was.toString(16)} at first`);
    }
    function loadBegun() {
        const file = DF[cpu.x];
        const img = images.find((i) => i.file === file && PLACES[i.name].phys(word(sym.fe_dst)) === i.phys0 && cpu.y === sym.BANK_PIC);
        loading = img ?? null;
    }

    // armed once the title's up: the start's work (over the lists and
    // objects) done, every file it loads in place
    function arm() {
        armed = true;
        for (const img of images) if (img.name !== "SpeechA" && img.name !== "WindowPic" && img.name !== "Docked") own(img);
        // the MOS's interrupt entry: its vector, to its JMP (IRQ1V)
        const os = (a) => ram[cpu.osOffset + (a - 0xc000)];
        mosEntry = new Set();
        let a = os(0xfffe) | (os(0xffff) << 8);
        for (let n = 0; n < 16; n++) {
            mosEntry.add(a);
            const opc = os(a);
            if (opc === 0x6c) break;                    // JMP (abs)
            a += opLen(opc);
        }
        lastField = 0;
        lastBeat = now();
    }

    // --- each step's top: the logic's state ---
    let maxLevel = 0, dockings = 0, missilesLaunched = 0, games = 0;
    let pendingPokes = [];
    let lastDocked = 0, lastMv = 0, wasMv = 0;
    function stepTop() {
        for (const [a, v] of pendingPokes) ram[a] = v;
        pendingPokes = [];
        if (!armed) return;
        const lvl = word(sym.level);
        if (lvl > maxLevel) maxLevel = lvl;
        if (ram[sym.docked] && !lastDocked) dockings++;
        lastDocked = ram[sym.docked];
        if (ram[sym.missile_view] && !lastMv) missilesLaunched++;
        // (the step the view ends doesn't clamp the speed: the next does)
        wasMv = lastMv;
        lastMv = ram[sym.missile_view];
        for (const [key, what] of invariants()) problem("state", key, what);
        if (gameSteps >= 0 && process.env.SOAK_TRACE) {
            const t = (trace[games] ??= []);
            t.push([...ram.slice(sym.rng_lag, sym.rng_lag + 12)].map((b) => b.toString(16).padStart(2, "0")).join("") +
                ` ${word(sym.pl_x).toString(16)} ${word(sym.pl_z).toString(16)} ${s16(sym.mouse_x)} ${s16(sym.mouse_y)} ${word(sym.sight_x)} ${word(sym.frame_count)} ${steps()}`);
        }
        if (gameSteps >= 0 && ++gameSteps === FRESH_STEPS) fresh();
    }

    // --- each game's start as the first's: the player idles for its first
    // FRESH_STEPS steps, and then the screens, the objects and the logic's
    // variables must be the first game's then. A new game seeds the random
    // numbers, so only what one game leaves to the next can differ: what the
    // ST carries too is made the same (CARRIED) or left out (CARRIES). ---
    const FRESH_STEPS = 40;
    // What the ST carries from game to game that changes a game's first
    // steps, made the first game's at each start: the frame count, the turn
    // (random32 adds it, and new_game draws numbers before it zeroes it),
    // the place the last game left the player (new_game's first dots are
    // round it, each random8 adding the last), the speed (the first step
    // moves by the last game's: new_game sets the speed's accumulator, not
    // the speed), F's fixed sight, Q's sound, H's every face, and the shapes'
    // animation frames and the beam's colour (animate_shapes's, in the ST's
    // program).
    const CARRIED = [["frame_count", 2], ["mouse_x", 2], ["pl_x", 2], ["pl_z", 2], ["speed", 2], ["sight_fixed", 1], ["sound_on", 1],
        ["all_faces", 1], ["beam_colour", 1], ["anim_frame", 32]];
    // ... and what it carries that changes nothing then: the silo's two
    // records (init_objects clears the others), the silo docked at, the
    // last bolt's target and shots (none drawn: their counts are 0), the
    // laser's last box (written, never read), the last missile's view, the
    // last speech asked for, Interrogate's entry, the K screen's keys, the
    // cheat's count of entries, the ground dots the last missile view saved,
    // the free stack past its top; and the port's own calls' vectors
    const CARRIES = /^(ob_\w+\+14[01]|dots_[xz]_(lo|hi)|cheat_count|docked_silo|bolt_target_[xy]|shot_\w+|laser_\w+|m_\w+|sample_\w+|int_entry|def_\w+|logic_vec|world_vec)(\+\d+)?$/;
    const carries = (a) => CARRIES.test(varName(a)) || (a >= sym.free_stack + ram[sym.free_n] && a < sym.free_stack + sym.SLOTS);
    let gameSteps = -1, freshRef = null, carried = null, freshDrawn = null, freshSkipped = 0, framesAtPlay = 0;
    const trace = {}, rtrace = {};
    const FRESH = [
        ["main RAM's screen", SCREEN, 0x8000], ["the shadow screen", SHADOW + SCREEN, 0x10000],
        ["the objects", sym.OBJECTS, SCREEN], ["the objects' ANDY fields", 0x8000, sym.ANDY_OBJECTS_END],
        ["the logic's workspace", sym.work_end, sym.logic_work_end], ["the logic's ANDY", sym.ANDY_OBJECTS_END, sym.logic_andy_end],
        ...(process.env.SOAK_TRACE ? [["the lists", sym.LISTS, sym.OBJECTS], ["zero page", 0, 0x100], ["the workspace", sym.WORK, sym.work_end]] : []),
    ];
    const VARS = ["ZeroPage", "Work", "Objects", "ObjectsAndy", "Lists", "LogicWork", "LogicAndy", "GameWork", "PanelAndy", "FrontAndy"]
        .flatMap((s) => secLabels[s] ?? []).filter((l) => l.top).sort((a, b) => a.addr - b.addr);
    const varName = (a) => {
        const l = lastAt(VARS, a);
        return l ? (l.addr === a ? l.name : `${l.name}+${a - l.addr}`) : `&${a.toString(16)}`;
    };
    // (the screens are compared only when the same frames were drawn: which
    // steps draw one goes by the time they take, decision 14, and so by the
    // drawing's caches, which a game may leave the next)
    function fresh() {
        const now = FRESH.map(([, a, b]) => ram.slice(a, b));
        const drawn = `${word(sym.frames) - framesAtPlay} ${ram[sym.draw_buffer]}`;
        if (!freshRef) {
            freshRef = now;
            freshDrawn = drawn;
            return;
        }
        if (drawn !== freshDrawn) freshSkipped++;
        FRESH.forEach(([name, a], i) => {
            if (i < 2 && drawn !== freshDrawn) return;
            const diff = [];
            for (let j = 0; j < now[i].length; j++) if (now[i][j] !== freshRef[i][j] && !(i >= 2 && carries(a + j))) diff.push(j);
            if (!diff.length) return;
            const at = (j) => (i < 2 ? `(${4 * (((j % 640) >> 3))}, ${((j / 640) | 0) * 8 + (j & 7)}) by ${writerRoutine(lastWriter[a + j - SCREEN])}` : varName(a + j));
            problem("fresh", name, `game ${games}'s ${name} after ${FRESH_STEPS} idle steps: ${diff.length} bytes not the first game's, ` +
                diff.slice(0, process.env.SOAK_TRACE ? 60 : 6).map((j) => `${at(j)} &${now[i][j].toString(16)} for &${freshRef[i][j].toString(16)}`).join(", "));
        });
    }
    const bcd = (v) => (v & 15) < 10 && v >> 4 < 10;
    function invariants() {
        const v = [];
        const lvl = word(sym.level);
        if (lvl < 1 || lvl > 34) v.push(["level", `level ${lvl}`]);
        if (word(sym.level_msg) > 0x32) v.push(["level_msg", `level_msg ${word(sym.level_msg)}`]);
        if (word(sym.missiles) > 2) v.push(["missiles", `missiles ${word(sym.missiles)}`]);
        if (word(sym.game_over) > 2) v.push(["game_over", `game_over ${word(sym.game_over)}`]);
        if (word(sym.launch_state) > 0x1e) v.push(["launch_state", `launch_state &${word(sym.launch_state).toString(16)}`]);
        if (ram[sym.cheat_count] > 1) v.push(["cheat_count", `cheat_count ${ram[sym.cheat_count]}`]);
        if (ram[sym.bolt_timer] > 4) v.push(["bolt_timer", `bolt_timer ${ram[sym.bolt_timer]}`]);
        const iris = word(sym.m_iris);
        if (iris > 0x80 || iris & 7) v.push(["m_iris", `m_iris &${iris.toString(16)}`]);
        if (ram[sym.shot_n] > sym.SHOTS) v.push(["shot_n", `shot_n ${ram[sym.shot_n]}`]);
        if (ram[sym.int_entry] > 17) v.push(["int_entry", `int_entry ${ram[sym.int_entry]}`]);
        if (ram[sym.n_slots] > sym.SLOTS) v.push(["n_slots", `n_slots ${ram[sym.n_slots]}`]);
        for (let i = 0; i < 4; i++) if (!bcd(ram[sym.score + i])) v.push(["score", `the score's byte ${i} &${ram[sym.score + i].toString(16)}, not BCD`]);
        for (let i = 0; i < 2; i++) if (!bcd(ram[sym.pending_score + i])) v.push(["pending", `pending_score's byte ${i} not BCD`]);
        // the player, as player_flight leaves it
        const y = s16(sym.pl_y);
        if (y < -1800 || y > -20) v.push(["pl_y", `pl_y ${y}`]);
        const mx = s16(sym.mouse_x), my = s16(sym.mouse_y);
        if (Math.abs(mx) > sym.MOUSE_X_MAX) v.push(["mouse_x", `mouse_x ${mx}`]);
        if (Math.abs(my) > sym.MOUSE_Y_MAX + 8) v.push(["mouse_y", `mouse_y ${my}`]);
        const sa = s16(sym.speed_acc);
        if (!ram[sym.missile_view] && !wasMv && (sa < -479 || sa > 0)) v.push(["speed_acc", `speed_acc ${sa}`]);
        // the free records: distinct, each free
        const fn = ram[sym.free_n];
        if (fn > sym.SLOTS) v.push(["free_n", `free_n ${fn}`]);
        else {
            const seen = new Set();
            for (let i = 0; i < fn; i++) {
                const s = ram[sym.free_stack + i];
                if (s >= sym.SLOTS) v.push(["free_slot", `free_stack[${i}] slot ${s}`]);
                else if (seen.has(s)) v.push(["free_twice", `slot ${s} twice on the free stack`]);
                else if (ram[sym.ob_type + s]) v.push(["free_used", `free slot ${s} has type ${ram[sym.ob_type + s]}`]);
                seen.add(s);
            }
        }
        // the objects
        for (let s = 0; s < sym.OB_SLOTS; s++) {
            const t = ram[sym.ob_type + s];
            if (t > 0x1c) v.push(["type", `slot ${s} type ${t}`]);
            if (ram[sym.ob_explosion + s] > 31) v.push(["explosion", `slot ${s} explosion frame ${ram[sym.ob_explosion + s]}`]);
            const ex = ram[sym.ob_exploding + s];
            if (ex !== 0 && ex !== 0xff) v.push(["exploding", `slot ${s} exploding &${ex.toString(16)}`]);
        }
        // the lists
        for (const [n, list] of [["coarse_n", "coarse_slots"], ["near_n", "near_slots"], ["draw_n", "draw_slots"]]) {
            const c = ram[sym[n]];
            if (c > sym.OB_SLOTS) v.push([n, `${n} ${c}`]);
            else for (let i = 0; i < c; i++) if (ram[sym[list] + i] >= sym.OB_SLOTS) v.push([list, `${list}[${i}] ${ram[sym[list] + i]}`]);
        }
        return v;
    }

    // --- each erase: the window of the screen about to be drawn (as
    // tools/erasecheck.mjs checks it) ---
    const TEXTS_OF_BIT = [[0], [1], [2], [3], [4], [5, 6], [7, 8, 9], [10, 11, 12]];
    const cellsOf = (t) => {
        const [x, y] = panel.places[t.place];
        const n = t.string === "num_text" ? 5 : panel.strings[t.string].length;
        return { x: x + 8 * (t.after ? panel.level_prefix : 0), y, n };
    };
    function kept(buf, x, y) {
        const bits = ram[sym.ps_texts + buf];
        for (let b = 0; b < 8; b++)
            if (bits & (1 << b))
                for (const id of TEXTS_OF_BIT[b]) {
                    const c = cellsOf(panel.texts[id]);
                    if (y >= c.y && y < c.y + 8 && x >= c.x && x < c.x + 8 * c.n) return true;
                }
        return false;
    }
    const PIX = [0x88, 0x44, 0x22, 0x11];
    const at = (x, y) => SCREEN + (y >> 3) * 640 + (x >> 2) * 8 + (y & 7);
    function stWindow(iris, life) {
        const want = new Map();
        for (let y = 10; y <= 130; y++)
            for (let x = sym.VIEW_XMIN; x <= sym.VIEW_XMAX; x += 4) {
                const r = y + iris;
                want.set(at(x, y), r <= 130 ? winRaw[((r >> 3) - 1) * 576 + ((x - sym.VIEW_XMIN) >> 2) * 8 + (r & 7)] : 0);
            }
        if (iris === 0) {
            const blocks = 17 - ((((life - 0xf) << 16) >> 20) & 0xf);
            let x = 0xd3;
            for (let b = 0; b < blocks; b++) {
                for (let px = x - 2; px <= x + 1; px++)
                    for (let y = 0x76; y < 0x7a; y++) want.set(at(px, y), want.get(at(px, y)) | (PIX[px & 3] & ram[sym.colour_map + 7]));
                x -= 6;
                if (b + 1 === 8 || b + 1 === 9) x -= 2;
            }
        }
        return want;
    }
    let erases = 0, mvWindows = 0, mvPending = -1;
    function erased() {
        if (!armed || phase !== "play") return;
        erases++;
        const buf = ram[sym.draw_buffer];
        const base = buf ? SHADOW : 0;
        if (ram[sym.mv_render]) {
            mvPending = buf;
            return;
        }
        if (ram[sym.win_shown + buf] !== 0xff) return;
        let lit = 0, first = null;
        for (let y = sym.VIEW_YMIN; y <= sym.VIEW_YMAX; y++)
            for (let c = 0; c < sym.WINDOW_COLS; c++) {
                const a = SCREEN + (y >> 3) * 640 + (y & 7) + (WIN_X0 + c) * 8;
                if (ram[base + a] && !kept(buf, 4 * (WIN_X0 + c), y)) {
                    lit++;
                    first ??= [4 * (WIN_X0 + c), y];
                }
            }
        if (lit) problem("erase", "left", `${lit} bytes of the window left lit after its erase, the first at (${first}), screen ${buf}`);
    }
    function windowDrawn() {
        if (mvPending < 0) return;
        const buf = mvPending;
        mvPending = -1;
        mvWindows++;
        const base = buf ? SHADOW : 0;
        const want = stWindow(ram[sym.m_iris], word(sym.m_life));
        let wrong = 0;
        for (const [a, v] of want) {
            const x = sym.VIEW_XMIN + (((a - SCREEN) % 640) >> 3) * 4, y = (((a - SCREEN) / 640) | 0) * 8 + ((a - SCREEN) & 7);
            if (ram[base + a] !== v && !kept(buf, x, y)) wrong++;
        }
        if (wrong) problem("erase", "mview", `the missile view's window at m_iris ${ram[sym.m_iris]}: ${wrong} bytes not the ST's after its erase`);
    }

    // --- the keys: the BBC's internal numbers ---
    const KEY = {
        SPACE: 0x62, SLASH: 0x68, LEFT: 0x19, RIGHT: 0x79, UP: 0x39, DOWN: 0x29, X: 0x42, C: 0x52, SEMI: 0x57, PERIOD: 0x67,
        RETURN: 0x49, COPY: 0x69, KPRETURN: 0x3c, ESCAPE: 0x70, DELETE: 0x59, F: 0x43, M: 0x65, L: 0x56, P: 0x37, Q: 0x10,
        S: 0x51, I: 0x25, N: 0x55, E: 0x22, J: 0x45, A: 0x41, R: 0x33, G: 0x53, K: 0x46, Y: 0x44, H: 0x54, Z: 0x61, T: 0x23,
        B: 0x64, U: 0x35, V: 0x63, COMMA: 0x66, D: 0x32, W: 0x21, O: 0x36, K3: 0x11, K8: 0x15, K2: 0x31, K4: 0x12, K6: 0x34,
        TAB: 0x60, SHIFT: 0x00, CTRL: 0x01, K1: 0x30, K0: 0x27, F1: 0x71,
    };
    const held = new Set();
    const down = (k) => {
        if (held.has(k)) return;
        held.add(k);
        cpu.sysvia.keyDownRaw([KEY[k] & 15, KEY[k] >> 4]);
    };
    const up = (k) => {
        if (!held.has(k)) return;
        held.delete(k);
        cpu.sysvia.keyUpRaw([KEY[k] & 15, KEY[k] >> 4]);
    };
    const upAll = () => {
        for (const k of [...held]) up(k);
        stick[0] = stick[1] = 0x8000;
        cpu.sysvia.setJoystickButton(0, false);
        cpu.sysvia.setJoystickButton(1, false);
    };
    const stick = [0x8000, 0x8000];
    for (const ch of [0, 1]) cpu.adconverter.setChannelSource(ch, { getValue: (c) => stick[c], dispose() {} });
    const note = (what) => {
        recent.push(`${secs().toFixed(2)}s ${what}`);
        if (recent.length > 40) recent.shift();
        if (LOG) console.log(`${secs().toFixed(2)}s step ${steps()} [${phase}] ${what}`);
    };

    // --- running: a field at a time, the engine watched after each ---
    class Stop extends Error {}
    const endAt = SECS * CYCLES;
    let lastSteps = 0, lastStepAt = 0, lastFrames = 0, lastFrameAt = 0;
    async function field(n = 1) {
        for (let i = 0; i < n; i++) {
            await tm.runFor(FIELD);
            if (fatal || now() >= endAt) throw new Stop();
            watch();
        }
    }
    // a wait inside an action: false once the phase has changed under it
    async function act(n, ph) {
        for (let i = 0; i < n; i++) {
            await field(1);
            if (phase !== ph) return false;
        }
        return true;
    }
    function watch() {
        const t = now();
        if (!armed) {
            if (t > 60 * CYCLES) problem("hang", "boot", "the title not up a minute after the start", { stop: true });
            return;
        }
        if (t - lastBeat > 5 * CYCLES)
            problem("hang", phase, `no heartbeat for ${((t - lastBeat) / CYCLES).toFixed(1)}s, the PC at ${where(physPc(cpu.pc))}`, { stop: true });
        if (steps() !== lastSteps) {
            lastSteps = steps();
            lastStepAt = t;
        } else if (phase === "play" && t - lastStepAt > 3 * CYCLES)
            problem("hang", "steps", `in play, no step for ${((t - lastStepAt) / CYCLES).toFixed(1)}s, the PC at ${where(physPc(cpu.pc))}`, { stop: true });
        if (word(sym.frames) !== lastFrames) {
            lastFrames = word(sym.frames);
            lastFrameAt = t;
        } else if (phase === "play" && t - lastFrameAt > 4 * CYCLES && t - lastStepAt < CYCLES)
            problem("hang", "frames", `in play, steps but no frame for ${((t - lastFrameAt) / CYCLES).toFixed(1)}s`);
        if (phase !== "play") lastStepAt = lastFrameAt = t;
    }

    // --- the player ---
    const D = (n) => n;                                  // (fields)
    async function tap(k, ph, hold = 5) {
        down(k);
        const ok = await act(hold, ph);
        up(k);
        return ok && (await act(5, ph));
    }
    // steering by the keys toward a heading and a height, and a speed
    function steer(wantHeading, wantY, wantSpeed) {
        const e = ((((wantHeading - word(sym.pl_heading)) & 0xfff) + 2048) & 0xfff) - 2048;
        const mx = s16(sym.mouse_x);
        const tx = Math.max(-sym.MOUSE_X_MAX, Math.min(sym.MOUSE_X_MAX, e * 2));
        if (mx < tx - 24) (up("LEFT"), down("RIGHT"));
        else if (mx > tx + 24) (up("RIGHT"), down("LEFT"));
        else (up("LEFT"), up("RIGHT"));
        if (wantY !== null) {
            const my = s16(sym.mouse_y);
            const ty = Math.max(-0x100, Math.min(0x100, (s16(sym.pl_y) - wantY) * 2));
            if (my < ty - 24) (up("UP"), down("DOWN"));
            else if (my > ty + 24) (up("DOWN"), down("UP"));
            else (up("UP"), up("DOWN"));
        }
        if (wantSpeed !== null) {
            const sp = -s16(sym.speed_acc);
            if (sp < wantSpeed - 20) (up("SLASH"), down("SPACE"));
            else if (sp > wantSpeed + 20) (up("SPACE"), down("SLASH"));
            else (up("SPACE"), up("SLASH"));
        }
        return e;
    }
    const bearing = (dx, dz) => Math.round((Math.atan2(dx, dz) / (2 * Math.PI)) * 4096) & 0xfff;
    const wrap16 = (v) => ((v & 0xffff) << 16) >> 16;
    const obWord = (lo, hi, s) => (ram[sym[lo] + s] | (ram[sym[hi] + s] << 8));
    const obPos = (s) => [obWord("ob_x_lo", "ob_x_hi", s), (obWord("ob_y_lo", "ob_y_hi", s) << 16) >> 16, obWord("ob_z_lo", "ob_z_hi", s)];
    function slotsOf(test) {
        const out = [];
        for (let s = 0; s < sym.SLOTS; s++) if (ram[sym.ob_type + s] && test(ram[sym.ob_type + s], s)) out.push(s);
        return out;
    }
    const SILO = 6;
    // a silo's mouth: d units out along the heading it docks on, which puts
    // its heading as drawn at 0
    function mouth(s, d) {
        const [x, y, z] = obPos(s);
        const h = (-obWord("ob_heading_lo", "ob_heading_hi", s)) & 0xfff;
        const a = (h / 4096) * 2 * Math.PI;
        return { x: (x - Math.round(d * Math.sin(a))) & 0xffff, z: (z - Math.round(d * Math.cos(a))) & 0xffff, y, h, sx: x, sz: z };
    }

    async function play() {
        const ph = "play";
        if (gameSteps >= 0 && gameSteps < FRESH_STEPS) {
            upAll();
            return void (await field(1));
        }
        if (ram[sym.docked]) return docked();
        if (ram[sym.missile_view]) return missileView();
        const what = weighted([
            [30, "cruise"], [14, "silo"], [12, "hunt"], [4, "ground"], [6, "missile"], [10, "command"], [5, "cheat"],
            [2, "escape"], [6, "level"], [1, "die"], [6, "teleport"], [4, "stick"], [3, "idle"], [2, "stop"],
        ]);
        if (what === "cruise") {
            note("cruise");
            const keys = ["LEFT", "RIGHT", "UP", "DOWN", "X", "C", "SEMI", "PERIOD", "SPACE", "SLASH", "RETURN", "COPY", "KPRETURN"];
            for (let n = between(3, 12); n > 0; n--) {
                const k = pick(keys);
                down(k);
                if (chance(0.3)) down(pick(keys));
                const ok = await act(between(2, 60), ph);
                upAll();
                if (!ok) return;
            }
        } else if (what === "silo" || what === "teleport") {
            const silos = slotsOf((t) => t === SILO);
            if (!silos.length) return;
            const s = pick(silos);
            const m = mouth(s, what === "teleport" ? 900 : 2600);
            if (what === "teleport") {
                note(`teleport to silo ${s}'s mouth`);
                pendingPokes = [
                    [sym.pl_x, m.x & 0xff], [sym.pl_x + 1, m.x >> 8], [sym.pl_z, m.z & 0xff], [sym.pl_z + 1, m.z >> 8],
                    [sym.pl_y, (m.y - 60) & 0xff], [sym.pl_y + 1, ((m.y - 60) >> 8) & 0xff],
                    [sym.pl_heading, m.h & 0xff], [sym.pl_heading + 1, m.h >> 8],
                ];
                if (!(await act(8, ph))) return;
            } else note(`steer at silo ${s}`);
            // to the mouth, then in, level with it, slowly
            let stage = what === "teleport" ? 1 : 0;
            for (let n = 0; n < 900 && !ram[sym.docked]; n++) {
                const px = word(sym.pl_x), pz = word(sym.pl_z);
                const tx = stage ? m.sx : m.x, tz = stage ? m.sz : m.z;
                const dx = wrap16(tx - px), dz = wrap16(tz - pz);
                if (!stage && Math.hypot(dx, dz) < 500) stage = 1;
                steer(bearing(dx, dz), stage ? m.y - 60 : -300, stage ? 120 : 300);
                if (!(await act(2, ph))) return upAll();
            }
            upAll();
            if (ram[sym.docked]) note(`docked at silo ${s}`);
        } else if (what === "hunt") {
            const foes = slotsOf((t) => t !== SILO && t !== 4 && t !== 9 && t !== 11 && t !== 22 && t !== 24);
            if (!foes.length) return;
            const s = pick(foes);
            note(`hunt slot ${s} (type ${ram[sym.ob_type + s]})`);
            for (let n = between(60, 300); n > 0 && ram[sym.ob_type + s] && !ram[sym.ob_exploding + s]; n--) {
                const [x, y, z] = obPos(s);
                const e = steer(bearing(wrap16(x - word(sym.pl_x)), wrap16(z - word(sym.pl_z))), Math.min(-40, y - 80), between(150, 479));
                if (Math.abs(e) < 96 && chance(0.6)) down("RETURN");
                else up("RETURN");
                if (!(await act(2, ph))) return upAll();
            }
            upAll();
        } else if (what === "ground") {
            note("down to the ground, fast");
            down("UP");
            down("SPACE");
            const ok = await act(between(50, 400), ph);
            upAll();
            if (!ok) return;
        } else if (what === "missile") {
            if (!word(sym.missiles) && ram[sym.cheat_mode]) (note("P"), await tap("P", ph));
            note("L");
            await tap("L", ph);
        } else if (what === "command") {
            const k = weighted([[3, "F"], [2, "Q"], [2, "S"], [3, "M"], [4, "N"], [2, "P"], [2, "I"], [1, "E"], [1, "H"], [1, "K"]]);
            note(`command ${k}`);
            await tap(k, ph);
        } else if (what === "cheat") {
            await cheat(ph);
        } else if (what === "escape") {
            // (in cheat mode now and then, for G's viewer on the title)
            if (chance(0.4)) ram[sym.cheat_mode] = 0xff;
            note(`Esc${ram[sym.cheat_mode] ? " in cheat mode" : ""}`);
            await tap("ESCAPE", ph);
        } else if (what === "level") {
            if (ram[sym.cheat_mode] && chance(0.5)) {
                note("N, N, N");
                for (let n = between(1, 6); n > 0; n--) if (!(await tap("N", ph))) return;
            } else {
                // the score's ten-thousands on, the level test's byte, a step
                // at a time: a level each
                const n = chance(0.3) ? between(5, 34) : between(1, 3);
                note(`the score's level byte on ${n} times`);
                for (let i = 0; i < n; i++) {
                    const b = ram[sym.score + 2];
                    pendingPokes.push([sym.score + 2, (b & 15) < 9 ? b + 1 : (b & 0xf0) < 0x90 ? (b & 0xf0) + 0x10 : 0]);
                    if (!(await act(between(8, 40), ph))) return;
                }
            }
        } else if (what === "die") {
            const go = between(1, 2);
            note(`game_over ${go}`);
            pendingPokes.push([sym.game_over, go], [sym.game_over + 1, 0]);
            await act(20, ph);
        } else if (what === "stick") {
            note("the stick");
            for (let n = between(3, 10); n > 0; n--) {
                stick[0] = between(0, 0xffff);
                stick[1] = between(0, 0xffff);
                cpu.sysvia.setJoystickButton(0, chance(0.3));
                cpu.sysvia.setJoystickButton(1, chance(0.2));
                const ok = await act(between(5, 50), ph);
                if (!ok) break;
            }
            upAll();
        } else if (what === "stop") {
            note("stop, the sight fixed");
            if (!ram[sym.sight_fixed]) if (!(await tap("F", ph))) return;
            down("SLASH");
            const ok = await act(between(100, 200), ph);
            upAll();
            if (ok && chance(0.6)) await cheat(ph, true);
        } else {
            note("idle");
            await act(between(10, 200), ph);
        }
    }
    // the cheat prompt: J S space A R G (twice turns cheat mode on or off,
    // stopped with the sight fixed), a wrong key, a timeout, or no J
    async function cheat(ph, right = false) {
        const seq = ["J", "S", "SPACE", "A", "R", "G"];
        const kind = right ? "right" : weighted([[5, "right"], [2, "wrong"], [1, "timeout"], [1, "first"], [1, "force"]]);
        if (kind === "force") {
            note("cheat_mode forced on");
            ram[sym.cheat_mode] = 0xff;
            return;
        }
        for (let n = kind === "right" ? 2 : 1; n > 0; n--) {
            note(`cheat prompt (${kind})`);
            if (!(await tap("DELETE", ph))) return;
            await field(between(2, kind === "first" ? 400 : 60));
            if (kind === "first") {
                await tapAny(pick(["K", "F", "SPACE", "RETURN", "L"]));
                return;
            }
            const wrongAt = kind === "wrong" ? between(1, 5) : -1;
            for (let i = 0; i < seq.length; i++) {
                if (i === wrongAt) await tapAny(pick(["F", "L", "P", "M", "N", "Q", "Z"]));
                else await tapAny(seq[i]);
                await field(kind === "timeout" && i === 3 ? 1600 : between(2, 30));
            }
            if (kind === "wrong") for (let i = 0; i < 6 && phase === "prompt"; i++) (await tapAny(pick(["Z", "B", "N"]))), await field(5);
        }
    }
    async function tapAny(k, hold = 5) {
        down(k);
        await field(hold);
        up(k);
        await field(3);
    }
    async function docked() {
        const ph = "play";
        // in the tunnel: on to its end
        if (word(sym.launch_state) !== 0x1e) return void (await act(10, ph));
        const what = weighted([[4, "interrogate"], [3, "pick"], [6, "launch"], [1, "cheat"], [1, "escape"], [2, "wait"], [1, "missile"]]);
        note(`docked: ${what}`);
        if (what === "interrogate") {
            await tap("I", ph);
        } else if (what === "pick") {
            await tap("P", ph);
        } else if (what === "launch") {
            await tap("SPACE", ph, between(2, 30));
            await act(between(20, 80), ph);
            if (chance(0.5)) await tap("L", ph);
        } else if (what === "cheat") {
            if (!ram[sym.sight_fixed]) await tap("F", ph);
            await cheat(ph, true);
        } else if (what === "escape") {
            await tap("ESCAPE", ph);
        } else if (what === "missile") {
            await tap("L", ph);
        } else await act(between(10, 300), ph);
    }
    async function missileView() {
        const ph = "play";
        const keys = ["LEFT", "RIGHT", "UP", "DOWN", "SPACE", "RETURN"];
        const k = pick(keys);
        down(k);
        await act(between(5, 40), ph);
        upAll();
        if (chance(0.05)) (note("L in the missile view"), await tap("L", ph));
    }
    async function interrogate() {
        const ph = "interrogate";
        for (let n = between(0, 20); n > 0 && phase === ph; n--) {
            await tapAny(chance(0.9) ? "SPACE" : pick(["Q", "L", "I", "P"]));
            await field(between(2, 100));
        }
        if (phase === ph) note("E");
        while (phase === ph) await tapAny("E");
    }
    async function prompt() {
        // (a prompt the player didn't mean: any key)
        await field(between(5, 100));
        if (phase === "prompt") await tapAny(pick(["Z", "J", "SPACE"]));
    }
    async function title() {
        const what = weighted([[10, "space"], [2, "key"], [2, "k"], [ram[sym.cheat_mode] ? 8 : 0, "g"], [2, "wait"], [1, "button"]]);
        const ph = "title";
        note(`title: ${what}`);
        if (what === "wait") {
            await act(between(1000, 2400), ph);
            return;
        }
        if (!(await act(between(20, 300), ph))) return;
        if (what === "space") await tapAny("SPACE", 10);
        else if (what === "key") await tapAny(pick(["RETURN", "A", "Z", "K1", "F1", "TAB", "COPY", "L", "M"]), 10);
        else if (what === "k") await tapAny("K", 10);
        else if (what === "g") await tapAny("G", 10);
        else {
            cpu.sysvia.setJoystickButton(1, true);
            await field(10);
            cpu.sysvia.setJoystickButton(1, false);
        }
        await field(20);
    }
    async function kscreen() {
        const pool = ["Z", "X", "C", "V", "B", "N", "M", "A", "S", "D", "H", "J", "K", "U", "T", "Y", "LEFT", "RIGHT", "UP", "DOWN",
            "SPACE", "SLASH", "PERIOD", "COMMA", "SEMI", "RETURN", "COPY", "K1", "K2", "TAB", "F1"];
        const keys = [];
        for (let i = 0; i < 6 && phase === "kscreen"; i++) {
            const k = pick(pool);
            keys.push(k);
            await field(between(5, 40));
            await tapAny(k);
        }
        note(`K screen: ${keys.join(" ")}`);
        await field(between(5, 100));
        if (phase === "kscreen") await tapAny(weighted([[5, "Y"], [2, "E"], [1, "Q"]]), 10);
        await field(10);
    }
    async function viewer() {
        const keys = ["PERIOD", "COMMA", "X", "S", "Y", "T", "Z", "A", "R", "E", "H", "P", "K3", "L", "K", "K8", "K2", "K4", "K6", "SPACE"];
        for (let n = between(3, 30); n > 0 && phase === "viewer"; n--) {
            await tapAny(pick(keys));
            await field(between(2, 60));
        }
        if (phase === "viewer") note("viewer: leaving");
        for (let n = 0; n < 40 && phase === "viewer"; n++) {
            await tapAny(pick(["Q", "ESCAPE"]));
            await field(between(5, 30));
            if (phase === "viewer" && n % 4 === 3) await tapAny("P");
        }
    }
    async function name() {
        const ph = "name";
        if (chance(0.15)) return void (await act(2000, ph));
        const pool = ["A", "B", "C", "D", "E", "M", "T", "K1", "K2", "SPACE", "COMMA", "PERIOD", "SLASH", "DELETE", "DELETE"];
        for (let n = between(0, 14); n > 0 && phase === ph; n--) {
            await tapAny(pick(pool));
            await field(between(2, 30));
        }
        if (phase === ph) await tapAny(chance(0.8) ? "RETURN" : "ESCAPE");
        await field(10);
    }
    async function anyKey(ph) {
        if (chance(0.2)) return void (await act(between(200, 1700), ph));
        if (!(await act(between(10, 300), ph))) return;
        await tapAny(pick(["SPACE", "RETURN", "A", "ESCAPE"]));
        await field(10);
    }

    // --- the run ---
    loadDisc(tm, disc, sym);
    const t0 = Date.now();
    try {
        for (;;) {
            if (phase === "play") await play();
            else if (phase === "title") await title();
            else if (phase === "kscreen") await kscreen();
            else if (phase === "viewer") await viewer();
            else if (phase === "interrogate") await interrogate();
            else if (phase === "prompt") await prompt();
            else if (phase === "name") await name();
            else if (phase === "rating" || phase === "endscreen" || phase === "ending") await anyKey(phase);
            else await field(5);
        }
    } catch (e) {
        if (!(e instanceof Stop)) throw e;
    }
    upAll();

    // what wrote outside the window, for the rules
    const screenRules = [...screenOut.entries()].sort();
    const byCtx = Object.values(splits.by);
    const result = {
        seed: SEED,
        secs: secs(),
        wall: (Date.now() - t0) / 1000,
        steps: steps(),
        frames: word(sym.frames),
        games,
        entered,
        maxLevel,
        dockings,
        missiles: missilesLaunched,
        erases,
        mvWindows,
        reachPast,
        freshSkipped,
        minS,
        minSAt: where(minSAt),
        worstField,
        splits: { n: splits.n, least: splits.least, late: byCtx.reduce((s, b) => s + b.late, 0),
            worst: Math.max(0, ...byCtx.map((b) => b.worst)), held: byCtx.reduce((s, b) => s + b.held, 0),
            worstHeld: Math.max(0, ...byCtx.map((b) => b.worstHeld)), by: splits.by },
        problems: [...problems.values()],
        allow: [...ALLOW],
        screenOut: Object.fromEntries(screenRules),
        census: CENSUS ? Object.fromEntries([...census].sort()) : undefined,
        trace: process.env.SOAK_TRACE ? trace : undefined,
        rtrace: process.env.SOAK_TRACE ? rtrace : undefined,
    };
    if (JSON_OUT) fs.writeFileSync(JSON_OUT, JSON.stringify(result, null, 1));
    console.log(summary(result));
    if (LOG) for (const [k, n] of screenRules) console.log(`  outside the window: ${k} ${n}`);
    process.exit(result.problems.some((p) => !ALLOW.has(p.kind)) ? 1 : 0);
}

// --- baron's listing (baron -v) ----------------------------------------------
// Each section's lines with bytes: an instruction, data (EQUB and the like,
// INCBIN) or a variable (SKIP), and its labels, each with the routine it's
// in (the last label outside a scope's braces).
function parseListing(text, sizes) {
    const OPS = new Set(("ADC AND ASL BCC BCS BEQ BIT BMI BNE BPL BRA BRK BVC BVS CLC CLD CLI CLV CMP CPX CPY DEC DEX DEY EOR INC INX INY " +
        "JMP JSR LDA LDX LDY LSR NOP ORA PHA PHP PHX PHY PLA PLP PLX PLY ROL ROR RTI RTS SBC SEC SED SEI STA STX STY STZ TAX TAY TRB TSB " +
        "TSX TXA TXS TYA").split(" "));
    const sections = [];
    const stack = [];
    let cur = null, depth = 0, top = null;
    for (const line of text.split("\n")) {
        let m;
        if ((m = /^SECTION (\w+)/.exec(line))) {
            cur = { name: m[1], items: [], labels: [] };
            sections.push(cur);
            stack.push(cur);
            continue;
        }
        if (/^ENDSECTION/.test(line)) {
            stack.pop();
            cur = stack[stack.length - 1] ?? null;
            continue;
        }
        if (line === "{") {
            depth++;
            continue;
        }
        if (line === "}") {
            depth--;
            continue;
        }
        if (!cur) continue;
        if ((m = /^  ([0-9A-F]{4})  \.([A-Za-z_]\w*)\s*$/.exec(line))) {
            const name = m[2];
            if (depth === 0) top = name;
            cur.labels.push({ addr: parseInt(m[1], 16), name, top: depth ? top : name });
            continue;
        }
        if ((m = /^  ([0-9A-F]{4})  (.{28})(.*)$/.exec(line))) {
            const field = m[2];
            const hex = field.replace("...", "").trim();
            if (!/^([0-9A-F]{2} ?)+$/.test(hex)) continue;
            const bytes = hex.split(/\s+/).map((h) => parseInt(h, 16));
            const mn = m[3].trim().split(/\s+/)[0];
            const kind = OPS.has(mn) ? 1 : mn === "SKIP" ? 4 : 3;
            cur.items.push({ addr: parseInt(m[1], 16), bytes, trunc: field.includes("..."), kind, len: bytes.length });
        }
    }
    // a truncated line's length: to the next line's address
    for (const sec of sections) {
        sec.items.sort((a, b) => a.addr - b.addr);
        sec.labels.sort((a, b) => a.addr - b.addr);
        sec.items.forEach((it, i) => {
            if (!it.trunc) return;
            const next = sec.items[i + 1];
            if (next) it.len = next.addr - it.addr;
            else if (sizes[sec.name]) it.len = sizes[sec.name].org + sizes[sec.name].size - it.addr;
            else throw new Error(`${sec.name}: its last line is cut short in the listing`);
        });
    }
    return sections;
}

// the 65C12's instruction lengths, for the MOS's interrupt entry: only
// those it uses need be right
function opLen(op) {
    if ([0x85, 0xa5, 0x29, 0xd0, 0xf0, 0x10, 0x30, 0x09, 0x49, 0xc9].includes(op)) return 2;
    if ([0x8d, 0xad, 0x4c, 0x6c, 0x2c, 0x20].includes(op)) return 3;
    return 1;
}
