# STARGLIDER — BBC Master 128 port
#
#   make          the disc (build/starglider.ssd) and the speed spike's build
#                 (build/spike)
#   make run      boot the disc in jsbeeb, screenshot to shots/run.png
#   make disc     the disc from a clean tree, as starglider.ssd (the README
#                 links it)
#   make check    sincos against the ST's sine table, the spike, the
#                 disc's erasing (tools/erasecheck.mjs) and its own disc
#                 reader (tools/disccheck.mjs)
#   make spike    the spike on every captured scene, checked against the
#                 ST's renderer, with its cycles (tools/scenecheck.py)
#   make logic    the port's game logic against the ST's, routine by
#                 routine, on every capture in build/steps (tools/logicrun.mjs)
#   make steps    capture the ST's logic in Hatari (tests/st/steps_*.txt;
#                 slow, needs Hatari)
#   make memory   what each region of the memory map holds (tools/memmap.py)
#   make fps      the disc's frames and steps a second (tools/fps.mjs)
#   make scenes   capture the scenes in Hatari (tests/st/*.txt; needs
#                 Hatari and EmuTOS, docs/research/st.md)
#   make fetch    download every version of the original into original/
#   make venv     the Python tools' environment (.venv: SkoolKit, Capstone,
#                 Pillow, NumPy)

# local.mk (not committed) can set BARON, as tools/worktree_setup.sh does.
-include local.mk
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
SOURCES  = $(wildcard src/*.6502 src/logic/*.6502)
GEN      = build/gen/shapes.6502 build/gen/types.6502 build/gen/line.6502 build/gen/linemode.6502 build/gen/rotate.6502 build/gen/xform.6502 build/gen/objects.6502 build/gen/handlers.6502 build/gen/collide.6502

# A failed step leaves no half-made target behind (asm.sh fails on a
# warning after baron has written its output).
.DELETE_ON_ERROR:

# Stamped into !BOOT, so a disc says what it is: UTC build time and the
# commit, with + if the tree had changes.
BUILD   := $(shell date -u '+%Y-%m-%d %H:%M UTC') $(shell git rev-parse --short HEAD 2>/dev/null || echo NOGIT)$(shell git diff --quiet HEAD -- . ':(exclude)starglider.ssd' 2>/dev/null || echo +)
TARGET   = build/starglider.ssd
DISC     = starglider.ssd

.PHONY: all run disc check spike logic steps memory fps scenes fetch venv clean

all: $(TARGET) build/spike/SPIKE

$(TARGET): $(SOURCES) $(GEN) build/gen/cockpit.bin | build
	$(ASM) -D 'BUILD="$(BUILD)"' -o $@ --title STARGLIDER --opt 3 --warn 2 --symbols $(@:.ssd=.json) src/main.6502

build:
	mkdir -p build

# The release disc, from a clean tree (so its stamp names the commit),
# copied to starglider.ssd, which the README links.
disc:
	@git diff --quiet HEAD -- . ':(exclude)$(DISC)' || { echo "commit first: the stamp would say +"; exit 1; }
	rm -f $(TARGET)
	$(MAKE) $(TARGET)
	cp $(TARGET) $(DISC)

run: $(TARGET)
	node tools/play.mjs '6,!run' shots/ --disc $(TARGET) --until start

# The ST's program, off TOSEC's clean image: the shapes and tables come
# from it at build time, so nothing of the original is committed.
$(PRG): | build/st
	@[ -f "$(ST_DISC)" ] || tools/fetch_original.sh
	$(PYTHON) -I tools/fat12.py "$(ST_DISC)" build/st/disc > /dev/null
	cp build/st/disc/AUTO/STAR.PRG $@

build/gen/shapes.6502 build/gen/types.6502 &: $(PRG) tools/mkshapes.py tools/st_shapes.py | build/gen
	$(PYTHON) -I tools/mkshapes.py $(PRG) build/gen

# The object handlers' tables (the handler by type, the arctan tables, the
# missiles' by type and by level).
build/gen/handlers.6502: $(PRG) tools/mkhandlers.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mkhandlers.py $(PRG) $@

build/gen/line.6502 build/gen/linemode.6502 &: tools/mkline.py | build/gen
	python3 -I tools/mkline.py build/gen

build/gen/rotate.6502: tools/mkrotate.py | build/gen
	python3 -I tools/mkrotate.py > $@

build/gen/xform.6502: tools/mkxform.py | build/gen
	python3 -I tools/mkxform.py > $@

build/gen/objects.6502 build/gen/objects.json &: tools/mkobjects.py | build/gen
	python3 -I tools/mkobjects.py build/gen

build/gen/collide.6502: $(PRG) tools/mkcollide.py | build/gen
	$(PYTHON) -I tools/mkcollide.py $(PRG) build/gen

# The cockpit, from the ST's RESULT.TRA (on its disc, beside STAR.PRG).
build/gen/cockpit.bin: $(PRG) tools/mkcockpit.py | build/gen
	$(PYTHON) -I tools/mkcockpit.py build/st/disc/RESULT.TRA --screen $@

build/spike/SPIKE: $(SOURCES) $(GEN) | build/spike
	$(ASM) --warn 2 -p build/spike --symbols build/spike/symbols.json src/spike.6502

build/st build/gen build/spike:
	mkdir -p $@

# The scenes as the port's inputs, with the ST renderer's results.
build/scenes/%/beeb.json: build/scenes/%/scenes.json $(PRG) tools/mkscene.py tools/st_render.py
	$(PYTHON) -I tools/mkscene.py $(PRG) $< $@

check: build/spike/SPIKE spike $(TARGET)
	$(PYTHON) -I tools/sinecheck.py $(PRG) build/spike
	node tools/erasecheck.mjs
	node tools/disccheck.mjs

spike: build/spike/SPIKE $(SCENES:%=build/scenes/%/beeb.json)
	@for s in $(SCENES); do \
	    echo "== $$s"; \
	    node tools/scenerun.mjs build/scenes/$$s/beeb.json build/scenes/$$s/run.json > /dev/null && \
	    $(PYTHON) -I tools/scenecheck.py build/scenes/$$s/beeb.json build/scenes/$$s/run.json --tolerance 8 || exit 1; \
	done

# The logic's routines, each on every capture (tools/logicrun.mjs's ROUTINES).
LOGIC    = animate flight keys handlers world world_after world_whole collide message frame_end post mine
STEPS    = $(patsubst tests/st/steps_%.txt,%,$(wildcard tests/st/steps_*.txt))

logic: build/spike/SPIKE
	@for s in $(STEPS); do for r in $(LOGIC); do \
	    [ -f build/steps/$$s/steps.json ] || { echo "no build/steps/$$s: make steps"; exit 1; }; \
	    node tools/logicrun.mjs build/steps/$$s/steps.json $$r || exit 1; \
	done; done

# The scripts time their keys in seconds, not the ST's frames, so a capture
# slowed by others running beside it plays a different game: a few at once.
STEPS_JOBS ?= 4
steps:
	mkdir -p build/steps
	@printf '%s\n' $(STEPS) | xargs -P $(STEPS_JOBS) -I{} sh -c '$(PYTHON) -I tools/st_steps.py run \
	    tests/st/steps_{}.txt build/steps/{} --disk "$(ST_STX)" --hatari $(HATARI) --tos $(HATARI_TOS) \
	    > build/steps/{}.log 2>&1'; tail -n1 build/steps/*.log

memory: $(TARGET)
	python3 -I tools/memmap.py build/starglider.json

fps: $(TARGET)
	node tools/fps.mjs 30

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
