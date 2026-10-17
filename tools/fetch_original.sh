#!/bin/sh
# Fetch every version of Starglider (1986) and its reference material into
# original/<machine>/, and check them against original/SHA256SUMS. Not
# committed: they are not ours to redistribute (original/README.md).
set -e
cd "$(dirname "$0")/../original"
SC=https://spectrumcomputing.co.uk
IA=https://archive.org/download
TOSEC_ST="$IA/Atari_ST_TOSEC_2012_04_23/Atari_ST_TOSEC_2012_04_23.zip"
get() { mkdir -p "$(dirname "$2")"; [ -f "$2" ] || curl -sfL "$1" -o "$2"; }
# getzip URL MEMBER DEST: one file out of a downloaded zip.
getzip() {
    [ -f "$3" ] && return
    mkdir -p "$(dirname "$3")"
    curl -sfL "$1" -o fetch.zip && unzip -p fetch.zip "$2" > "$3" && rm fetch.zip
}

# Atari ST: Argonaut's original (TOSEC's clean image, the protected master
# as Pasti STX, and the EMT crack, which splits the pictures out).
ST="Atari%20ST%20%5BTOSEC%5D/Games"
getzip "$TOSEC_ST/$ST/Atari%20ST%20-%20Games%20-%20%5BST%5D%20%28TOSEC%202011-12-19%29/Starglider%20%281987%29%28Rainbird%29.zip" \
    "Starglider (1987)(Rainbird).st" "st/Starglider (1987)(Rainbird).st"
getzip "$TOSEC_ST/$ST/Atari%20ST%20-%20Games%20-%20%5BSTX%5D%20%28TOSEC-v2011-03-20_CM%29/Starglider%20%281987%29%28Rainbird%29.zip" \
    "Starglider (1987)(Rainbird).stx" "st/Starglider (1987)(Rainbird).stx"
get "$IA/Starglider_1987_Rainbird_m_EMT/Starglider_1987_Rainbird_m_EMT.st" "st/Starglider (1987)(Rainbird)[m EMT].st"

# Amiga: Argonaut's port of the ST.
get "$IA/starglider-amiga/Starglider%20(1987)(Rainbird).adf" "amiga/Starglider (1987)(Rainbird).adf"

# ZX Spectrum: Realtime Games' 8-bit version (ZXDB entry 4863).
getzip "$SC/pub/sinclair/games/s/Starglider128.tap.zip" STARGLD1.TAP zx/Starglider128.tap
getzip "$SC/pub/sinclair/games/s/Starglider48.tap.zip" STARGLDR.TAP zx/Starglider48.tap
for v in 1 2 3; do
    for s in 1 2; do
        getzip "$SC/pub/sinclair/games/s/StargliderV$v.tzx.zip" \
            "Starglider - Release $v - Side $s.tzx" "zx/Starglider - Release $v - Side $s.tzx"
    done
done
getzip "$SC/pub/sinclair/games/s/Starglider.dsk.zip" Starglider.dsk "zx/Starglider (+3).dsk"
get "$IA/zx_Starglider_1986_Rainbird_Software_128K/Starglider_1986_Rainbird_Software_128K.z80" zx/Starglider128.z80
get "$SC/pub/sinclair/games-info/s/Starglider.txt" zx/Starglider.txt
get "$SC/zxdb/sinclair/entries/0004863/Starglider(EN).pdf" "zx/Starglider(EN).pdf"
get "$SC/zxdb/sinclair/entries/0004863/Starglider(EN)_novella.pdf" "zx/Starglider(EN)_novella.pdf"
get "$SC/pub/sinclair/games-maps/s/Starglider.jpg" zx/Starglider_map.jpg
get "$SC/pub/sinclair/games-extras/Starglider_KeyboardMap.jpg" zx/Starglider_KeyboardMap.jpg
get "$SC/pub/sinclair/screens/in-game/s/Starglider.gif" zx/Starglider.gif
get "$SC/pub/sinclair/screens/load/s/scr/Starglider.scr" zx/Starglider.scr

# Amstrad CPC: Realtime Games again.
get "$IA/Starglider_1986_Rainbird_Software/Starglider_1986_Rainbird_Software.dsk" cpc/Starglider.dsk

# The 6502 versions, by Solid Image: Commodore 64 and Apple II.
get "$IA/d64_Starglider_1986_Rainbird_Software/Starglider_1986_Rainbird_Software.d64" c64/Starglider.d64
get "$IA/a2_Starglider_1986_Rainbird/Starglider_1986_Rainbird.do" apple2/Starglider.do

# IBM PC (CGA): Realtime Games.
get "$IA/msdos_Starglider_1986/Starglider_1986.zip" pc/Starglider_1986.zip

sha256sum -c --quiet SHA256SUMS
