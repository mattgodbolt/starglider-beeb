# STARGLIDER — BBC Master 128 port
#
#   make          the speed spike's build (build/spike: SPIKE, SHAPES, SINE)
#   make check    the sine table against the ST's, and the spike
#   make spike    the spike on every captured scene, checked against the
#                 ST's renderer, with its cycles (tools/scenecheck.py)
#   make scenes   capture the scenes in Hatari (tests/st/*.txt; needs
#                 Hatari and EmuTOS, docs/research/st.md)
#   make fetch    download every version of the original into original/
#   make venv     the Python tools' environment (.venv: SkoolKit, Capstone,
#                 Pillow, NumPy)

BARON   ?= $(firstword $(wildcard ../baron/build/src/baron) baron)
# Baron, failing on a warning too.
ASM      = BARON=$(BARON) tools/asm.sh
PYTHON  ?= .venv/bin/python
HATARI  ?= ../hatari/build/src/hatari
HATARI_TOS ?= ../hatari/emutos/emutos-256k-1.3/etos256uk.img
ST_DISC  = original/st/Starglider (1987)(Rainbird).st
ST_STX   = original/st/Starglider (1987)(Rainbird).stx
PRG      = build/st/STAR.PRG
SCENES   = flight towers docked
SOURCES  = $(wildcard src/*.6502)
GEN      = build/gen/shapes.6502 build/gen/types.6502 build/gen/line.6502

# A failed step leaves no half-made target behind (asm.sh fails on a
# warning after baron has written its output).
.DELETE_ON_ERROR:

.PHONY: all check spike scenes fetch venv clean

all: build/spike/SPIKE

# The ST's program, off TOSEC's clean image: the shapes and tables come
# from it at build time, so nothing of the original is committed.
$(PRG): | build/st
	@[ -f "$(ST_DISC)" ] || tools/fetch_original.sh
	$(PYTHON) -I tools/fat12.py "$(ST_DISC)" build/st/disc > /dev/null
	cp build/st/disc/AUTO/STAR.PRG $@

build/gen/shapes.6502 build/gen/types.6502 &: $(PRG) tools/mkshapes.py tools/st_shapes.py | build/gen
	$(PYTHON) -I tools/mkshapes.py $(PRG) build/gen

build/gen/line.6502: tools/mkline.py | build/gen
	python3 -I tools/mkline.py > $@

build/spike/SPIKE: $(SOURCES) $(GEN) | build/spike
	$(ASM) --warn 2 -p build/spike --symbols build/spike/symbols.json src/spike.6502

build/st build/gen build/spike:
	mkdir -p $@

# The scenes as the port's inputs, with the ST renderer's results.
build/scenes/%/beeb.json: build/scenes/%/scenes.json $(PRG) tools/mkscene.py tools/st_render.py
	$(PYTHON) -I tools/mkscene.py $(PRG) $< $@

check: build/spike/SPIKE spike
	$(PYTHON) -I tools/sinecheck.py $(PRG) build/spike/SINE

spike: build/spike/SPIKE $(SCENES:%=build/scenes/%/beeb.json)
	@for s in $(SCENES); do \
	    echo "== $$s"; \
	    node tools/scenerun.mjs build/scenes/$$s/beeb.json build/scenes/$$s/run.json > /dev/null && \
	    $(PYTHON) -I tools/scenecheck.py build/scenes/$$s/beeb.json build/scenes/$$s/run.json --tolerance 1 || exit 1; \
	done

# Capturing is slow (Hatari runs in real time) and needs Hatari, so it's
# its own target; the captures stay in build/scenes.
scenes:
	mkdir -p build/scenes
	@for s in $(SCENES); do \
	    $(PYTHON) -I tools/st_scenes.py run tests/st/$$s.txt build/scenes/$$s \
	        --disk "$(ST_STX)" --hatari $(HATARI) --tos $(HATARI_TOS) > build/scenes/$$s.log 2>&1 & \
	done; wait; cat build/scenes/*.log

fetch:
	tools/fetch_original.sh

venv:
	uv sync

clean:
	rm -rf build/spike build/gen
