#!/bin/sh
# beeb_linebench.sh WORKDIR: fetch and build the line routines that
# tools/beeb_linebench.mjs times, then run it.
#
# Needs beebasm ($BEEBASM; the snap build cannot read /tmp), baron ($BARON, default ../baron/build/src/baron), ca65/ld65
# ($CC65BIN, a directory; default: on PATH) and node, with jsbeeb beside this
# project (../jsbeeb). Third-party sources are cloned into WORKDIR at pinned
# commits and stay there: nothing is copied into the project.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
work=${1:?usage: beeb_linebench.sh WORKDIR}
mkdir -p "$work"
work=$(cd "$work" && pwd)
BEEBASM=${BEEBASM:-beebasm}
BARON=${BARON:-$here/../../baron/build/src/baron}
CA65=${CC65BIN:+$CC65BIN/}ca65
LD65=${CC65BIN:+$CC65BIN/}ld65

fetch() { # repo commit dir
    if [ ! -d "$work/$3" ]; then
        git clone -q "https://github.com/$1.git" "$work/$3"
    fi
    git -C "$work/$3" checkout -q "$2"
}

# kieranhj/line-test: Elite-style, RTW, NJ and Tricky routines for MODE 4S.
fetch kieranhj/line-test 969dfd3 line-test
cp "$here/beeb_linebench_m4.asm" "$work/line-test/"
for h in 0 1; do
    (cd "$work/line-test" && "$BEEBASM" -i beeb_linebench_m4.asm -D HAMILTONIAN_12=$h) > "$work/m4-$h.out"
done
# Each PRINT line is name/address pairs.
grep -E '^start' -A1 "$work/m4-0.out" > "$work/LINEM4.sym"
grep -E '^start' -A1 "$work/m4-1.out" > "$work/LINEM4H.sym"
mv "$work/line-test/LINEM4" "$work/line-test/LINEM4H" "$work/"

# Master Elite as Mark Moxon's repository assembles it (BCODE, unencrypted).
fetch markmoxon/elite-source-code-bbc-master b892ec6 elite-master
cp "$work/elite-master/3-assembled-output/BCODE.unprot.bin" "$work/"

# ebenupton/virus raster.s: MODE 2, 128x160, 512-byte rows. Each line is
# independent here, so the wrapper pays init_base every time, as a lone line
# would; chained edges skip it. Buffer 1 (&5800) has no overflow guard.
fetch ebenupton/virus 468719e virus
cat > "$work/virus/beeb_bench_raster.s" <<'ASM'
.include "raster_zp.inc"
bench_line:
    JSR init_base
    LDA #$15                ; colour 7, right-pixel form
    JMP draw_line
bench_init:
    LDA #$58
    JMP set_page
.include "raster.s"
ASM
cat > "$work/virus/beeb_bench.cfg" <<'CFG'
MEMORY { CODE: start = $1000, size = $5000, file = %O; }
SEGMENTS { CODE: load = CODE, type = rw; }
CFG
(cd "$work/virus" && "$CA65" --cpu 6502 -g -o beeb_bench_raster.o beeb_bench_raster.s &&
    "$LD65" -C beeb_bench.cfg -Ln beeb_bench_raster.lbl -o "$work/RASTERM2" beeb_bench_raster.o)
# ld65's labels: "al 001000 .name"
awk '{ printf "%s %s\n", substr($3, 2), substr($2, 3) }' "$work/virus/beeb_bench_raster.lbl" > "$work/RASTERM2.sym"
echo "start 1000" >> "$work/RASTERM2.sym"

# Our MODE 1 routine: NJ's design at 2 bits a pixel (tools/beeb_line_m1.py).
python3 -I "$here/beeb_line_m1.py" > "$work/line_m1.6502"
"$BARON" --warn 2 "$work/line_m1.6502" -p "$work" > "$work/LINEM1.sym"

cat > "$work/targets.json" <<'JSON'
[
  { "name": "Eben's raster.s (virus, MODE 2)", "bin": "RASTERM2", "entry": "bench_line", "init": "bench_init",
    "zp": [36, 37, 38, 39], "endpoint": "open",
    "screen": { "base": 22528, "rowBytes": 512, "bpp": 4, "width": 128, "height": 160 } },
  { "name": "NJ-style, MODE 1 (ours)", "bin": "LINEM1", "entry": "line", "init": "colour_init",
    "zp": [112, 113, 114, 115], "endpoint": "closed",
    "screen": { "base": 12288, "rowBytes": 512, "bpp": 2, "width": 256, "height": 160 } }
]
JSON

node "$here/beeb_linebench.mjs" "$work"
