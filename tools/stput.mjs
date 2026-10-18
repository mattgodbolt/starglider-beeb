// The ST's logic state put into the port's memory, by the map
// (tools/stmap.py): every variable declared {ST address kind} and every
// object field, as tools/logicrun.mjs puts them (its items, the put half),
// for tools/panelcheck.mjs.
//
//   const put = stPut(map, steps, ram);   put(regions) puts a point's state
//
// regions is a point's state as byte arrays by region name; steps the
// capture (tools/st_steps.py's steps.json, for its regions); ram jsbeeb's
// memory array (ANDY at &8000, as the port's addresses have it).
export function slotOf(map, ptr) {
    if (ptr === 0) return 0xff;
    if (ptr === 0x1218) return 140;
    if (ptr === 0x1258) return 141;
    const s = (ptr - (0x5bf00 + map.records.offset)) / map.records.size;
    if (!Number.isInteger(s) || s < 0 || s >= 140) throw new Error(`not a record: &${ptr.toString(16)}`);
    return s;
}

export function regionsAt(frame, point) {
    const p = frame.points[point];
    if (!p) return null;
    const out = {};
    for (const [name, hex] of Object.entries(p)) out[name] = Buffer.from(hex, "hex");
    return out;
}

export function stPut(map, steps, ram) {
    const stLong = (r, addr) => {
        for (const [name, start, n] of steps.regions)
            if (addr >= start && addr + 4 <= start + n) return r[name].readUInt32BE(addr - start);
        throw new Error(`&${addr.toString(16)} isn't in the capture's regions`);
    };
    const puts = [];
    for (const v of map.variables) {
        const at = v.at;
        const st = (r) => r[v.region];
        const k = v.kind;
        if (k === "byte") puts.push((r) => (ram[at] = st(r)[v.offset]));
        else if (k === "word")
            puts.push((r) => {
                ram[at] = st(r)[v.offset + 1];
                ram[at + 1] = st(r)[v.offset];
            });
        else if (k === "word8") puts.push((r) => (ram[at] = st(r)[v.offset + 1]));
        else if (k === "long")
            puts.push((r) => {
                for (let i = 0; i < 4; i++) ram[at + i] = st(r)[v.offset + 3 - i];
            });
        else if (k === "raw") puts.push((r) => ram.set(st(r).subarray(v.offset, v.offset + v.count), at));
        else if (k === "wlo" || k === "whi" || k === "barr") {
            const lo = k === "wlo" ? 1 : 0;
            puts.push((r) => {
                for (let i = 0; i < v.count; i++) ram[at + i] = st(r)[v.offset + i * v.stride + lo];
            });
        } else if (k === "slots")
            puts.push((r) => {
                for (let i = 0; i < v.count; i++) ram[at + i] = slotOf(map, st(r).readUInt32BE(v.offset + 4 * i));
            });
        else if (k === "index")
            puts.push((r) => {
                const e = (st(r).readUInt32BE(v.offset) - v.base) / v.stride;
                if (Number.isInteger(e) && e >= 0 && e <= 255) ram[at] = e;
            });
        else if (k === "list")
            puts.push((r) => {
                const n = r[v.count_region].readUInt16BE(v.count_offset);
                const p = st(r).readUInt32BE(v.offset);
                ram[v.count_at] = n;
                for (let i = 0; i < n; i++) ram[at + n - 1 - i] = slotOf(map, stLong(r, p + 4 * i));
            });
        else if (k === "slotsdown")
            puts.push((r) => {
                for (let i = 0; i < v.count; i++) ram[at + i] = slotOf(map, st(r).readUInt32BE(v.offset - 4 * (i + 1)));
            });
        else if (k === "slot") puts.push((r) => (ram[at] = slotOf(map, st(r).readUInt32BE(v.offset))));
        else throw new Error(`${v.name}: kind ${k}`);
    }
    const rec = (r, s) =>
        s < 140
            ? r[map.records.region].subarray(map.records.offset + 64 * s, map.records.offset + 64 * s + 64)
            : r[map.records.silo.region].subarray(64 * (s - 140), 64 * (s - 140) + 64);
    for (const f of map.objects) {
        const [lo, hi] = f.at;
        for (let s = 0; s < f.slots; s++) {
            if (f.kind === "byte") puts.push((r) => (ram[lo + s] = rec(r, s)[f.field]));
            else if (f.kind === "word8") puts.push((r) => (ram[lo + s] = rec(r, s)[f.field + 1]));
            else if (f.kind === "word")
                puts.push((r) => {
                    ram[lo + s] = rec(r, s)[f.field + 1];
                    ram[hi + s] = rec(r, s)[f.field];
                });
        }
    }
    return (regions) => {
        for (const p of puts) p(regions);
    };
}
