# STARGLIDER — BBC Master 128 port
#
#   make          the disc (build/starglider.ssd) and the speed spike's build
#                 (build/spike)
#   make run      boot the disc in jsbeeb, screenshot to shots/run.png
#   make disc     the disc from a clean tree, as starglider.ssd (the README
#                 links it)
#   make check    sincos against the ST's sine table, the spike, the
#                 disc's erasing (tools/erasecheck.mjs), its own disc
#                 reader (tools/disccheck.mjs), its controls
#                 (tools/inputcheck.mjs), its front end's flows
#                 (tools/frontcheck.mjs), the cheat prompt, Interrogate
#                 and G's model viewer (tools/modalcheck.mjs), the level
#                 change's flash and fade (tools/flashcheck.mjs), its sound
#                 effects (make sfx), its speech (make speech), its title
#                 song (make tune), the raster on jsbeeb's CRTC and the
#                 palette split on it (tools/fieldcheck.mjs), and a short
#                 soak (tools/soak.mjs)
#   make soak     the whole disc played by a random player for a long time,
#                 a seed a process, watched for crashes, hangs, memory
#                 written where it shouldn't be and state the ST can't
#                 reach (tools/soak.mjs; SOAK_SEEDS, SOAK_SECS, SOAK_JOBS)
#   make sfx      the disc's sound effects against the ST's YM writes
#                 (tools/sfxcheck.mjs, on build/sfx's capture)
#   make speech   the disc's speech against its packed levels, and a WAV of
#                 each clip as the chip plays it (tools/speechcheck.mjs)
#   make sfxcapture  capture the ST's sound effects in Hatari
#                 (tests/st/sfx_all.txt; slow, needs Hatari)
#   make song     the title song's candidates as the SN76489 would play
#                 them, as WAVs in build/song/wav (decision 5,
#                 docs/research/song.md)
#   make tune     the disc's title song against the Spectrum 128K's player
#                 and the conversion's model, tick by tick, its bass's edges
#                 timed, and its render against the model's
#                 (tools/songcheck.mjs, tools/songcompare.py)
#   make spike    the spike on every captured scene, checked against the
#                 ST's renderer, with its cycles (tools/scenecheck.py)
#   make logic    the port's game logic against the ST's, routine by
#                 routine and a whole step, on every capture in build/steps
#                 (tools/logicrun.mjs)
#   make panel    the panel drawn from every capture's frames, pixel for
#                 pixel against the ST's formulas (tools/panelcheck.mjs)
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
SCENES   = flight towers docked missile
SOURCES  = $(wildcard src/*.6502 src/logic/*.6502)
GEN      = build/gen/shapes.6502 build/gen/types.6502 build/gen/anim.6502 build/gen/line.6502 build/gen/linemode.6502 build/gen/rotate.6502 build/gen/rotate_data.6502 build/gen/xform.6502 build/gen/objects.6502 build/gen/handlers.6502 build/gen/collide.6502 build/gen/levels.6502 build/gen/sight.6502 build/gen/ground.6502 build/gen/window.6502 build/gen/panel.6502 build/gen/sfx.6502 build/gen/speech.6502 build/gen/speech_clips.6502 build/gen/interrogate.6502 build/gen/song.6502

# A failed step leaves no half-made target behind (asm.sh fails on a
# warning after baron has written its output).
.DELETE_ON_ERROR:

# Stamped into !BOOT, so a disc says what it is: UTC build time and the
# commit, with + if the tree had changes.
BUILD   := $(shell date -u '+%Y-%m-%d %H:%M UTC') $(shell git rev-parse --short HEAD 2>/dev/null || echo NOGIT)$(shell git diff --quiet HEAD -- . ':(exclude)starglider.ssd' 2>/dev/null || echo +)
TARGET   = build/starglider.ssd
DISC     = starglider.ssd

.PHONY: all run disc check spike logic view panel rot sfx speech sfxcapture song tune steps memory fps scenes fetch venv clean soak

all: $(TARGET) build/spike/SPIKE

$(TARGET): $(SOURCES) $(GEN) build/gen/cockpit.bin build/gen/front.6502 build/gen/front_init.6502 build/gen/panel_start.6502 | build
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
	node tools/play.mjs '3,!run' shots/ --disc $(TARGET) --until start_loaded

# The ST's program, off TOSEC's clean image: the shapes and tables come
# from it at build time, so nothing of the original is committed.
$(PRG): | build/st
	@[ -f "$(ST_DISC)" ] || tools/fetch_original.sh
	$(PYTHON) -I tools/fat12.py "$(ST_DISC)" build/st/disc > /dev/null
	cp build/st/disc/AUTO/STAR.PRG $@

build/gen/shapes.6502 build/gen/types.6502 build/gen/anim.6502 &: $(PRG) tools/mkshapes.py tools/st_shapes.py | build/gen
	$(PYTHON) -I tools/mkshapes.py $(PRG) build/gen

# The object handlers' tables (the handler by type, the arctan tables, the
# missiles' by type and by level).
build/gen/handlers.6502: $(PRG) tools/mkhandlers.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mkhandlers.py $(PRG) $@

build/gen/line.6502 build/gen/linemode.6502 &: tools/mkline.py | build/gen
	python3 -I tools/mkline.py build/gen

build/gen/rotate.6502 build/gen/rotate_data.6502 &: tools/mkrotate.py | build/gen
	python3 -I tools/mkrotate.py build/gen/rotate.6502 build/gen/rotate_data.6502

build/gen/xform.6502: tools/mkxform.py | build/gen
	python3 -I tools/mkxform.py > $@

# The ground dots' rotation (src/view_under.6502), for ground_dots' decision
# and their drawing, with the bound on its terms that the decision takes
# checked for every entry and offset (tools/groundcheck.py, about a minute).
build/gen/ground.6502: tools/mkground.py tools/groundcheck.py | build/gen
	$(PYTHON) -I tools/groundcheck.py
	python3 -I tools/mkground.py > $@

# The gunsight's pixels, from the ST's STAR.PRG.
build/gen/sight.6502: $(PRG) tools/mksight.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mksight.py $(PRG) $@

build/gen/objects.6502 build/gen/objects.json &: tools/mkobjects.py | build/gen
	python3 -I tools/mkobjects.py build/gen

build/gen/collide.6502: $(PRG) tools/mkcollide.py | build/gen
	$(PYTHON) -I tools/mkcollide.py $(PRG) build/gen

# The sound effects' tables, from the ST's STAR.PRG.
build/gen/sfx.6502 build/gen/sfx.json &: $(PRG) tools/mksfx.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mksfx.py $(PRG) build/gen/sfx.6502 build/gen/sfx.json

# Clare Edgeley's speech, from the ST's STAR.PRG, packed for the SN76489 in
# three areas, the logic bank's after the effects' tables.
build/gen/speech.6502 build/gen/speech_clips.6502 build/gen/speech_a.bin build/gen/speech_b.bin build/gen/speech_c.bin build/gen/speech.json &: $(PRG) build/gen/sfx.json tools/mkspeech.py tools/st_samples.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mkspeech.py $(PRG) build/gen/sfx.json build/gen

# Interrogate's types, texts and glyphs, DOCKED's data (src/interrogate.6502),
# from the ST's STAR.PRG.
build/gen/interrogate.6502 build/gen/interrogate.json &: $(PRG) tools/mkinterrogate.py tools/mkpanel.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mkinterrogate.py $(PRG) build/gen/interrogate.6502 build/gen/interrogate.json

# David Lowe's title tune (decision 5): its player's data from the Spectrum
# 128K's bank 6, as the capture has it (tools/zx_song.py), and the
# conversion's constants, checked against tools/mksong.py's model.
build/gen/song.6502: build/zx/song.json tools/mksongdata.py tools/mksong.py tools/zx_song.py | build/gen
	$(PYTHON) -I tools/mksongdata.py build/zx/song.json $@

# The level layouts (init_objects's), from the ST's STAR.PRG.
build/gen/levels.6502: $(PRG) tools/mklevels.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mklevels.py $(PRG) build/gen

# The panel's font, strings, waveforms and colours, from STAR.PRG (and the
# few pixels of RESULT.TRA it changes without covering).
build/gen/panel.6502 build/gen/panel.json build/gen/panel_start.6502 &: $(PRG) tools/mkpanel.py tools/mkcockpit.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mkpanel.py $(PRG) build/st/disc/RESULT.TRA build/gen/panel.6502 build/gen/panel.json build/gen/panel_start.6502

# The front end's data: the title packed, the font, the texts, the keys
# (from the ST's STAR.PRG and TITLE.TRA), and the high scores for the start.
build/gen/front.6502 build/gen/front_init.6502 build/gen/front.json &: $(PRG) tools/mkfront.py tools/mkcockpit.py tools/st_prg.py | build/gen
	$(PYTHON) -I tools/mkfront.py $(PRG) build/st/disc/TITLE.TRA build/gen/front.6502 build/gen/front_init.6502 build/gen/front.json

# The cockpit, from the ST's RESULT.TRA (on its disc, beside STAR.PRG).
build/gen/cockpit.bin: $(PRG) tools/mkcockpit.py | build/gen
	$(PYTHON) -I tools/mkcockpit.py build/st/disc/RESULT.TRA --screen $@

# The missile view's window, from the same picture (and unpacked, for
# tools/viewrun.mjs).
build/gen/window.6502 build/gen/window.raw &: $(PRG) tools/mkcockpit.py | build/gen
	$(PYTHON) -I tools/mkcockpit.py build/st/disc/RESULT.TRA --window build/gen/window.6502 build/gen/window.raw

build/spike/SPIKE: $(SOURCES) $(GEN) | build/spike
	$(ASM) --warn 2 -p build/spike --symbols build/spike/symbols.json src/spike.6502

build/st build/gen build/spike:
	mkdir -p $@

# The scenes as the port's inputs, with the ST renderer's results.
build/scenes/%/beeb.json: build/scenes/%/scenes.json $(PRG) tools/mkscene.py tools/st_render.py
	$(PYTHON) -I tools/mkscene.py $(PRG) $< $@

check: build/spike/SPIKE spike panel view rot sfx speech tune $(TARGET) build/gen/front.json build/starglider.lst
	$(PYTHON) -I tools/sinecheck.py $(PRG) build/spike
	node tools/erasecheck.mjs
	node tools/disccheck.mjs
	node tools/inputcheck.mjs
	node tools/frontcheck.mjs
	node tools/modalcheck.mjs
	node tools/flashcheck.mjs
	node tools/fieldcheck.mjs
	node tools/soak.mjs --seeds $(CHECK_SOAK_SEEDS) --jobs 4 --secs $(CHECK_SOAK_SECS) $(SOAK_ALLOWING) --out build/soak/check

# baron's listing of the disc's program, which tells tools/soak.mjs each
# file's code from its data and variables (it checks the disc's files
# against it). The stamp isn't the disc's: only !BOOT holds it.
build/starglider.lst: $(SOURCES) $(GEN) build/gen/cockpit.bin build/gen/front.6502 build/gen/front_init.6502 build/gen/panel_start.6502 | build
	$(BARON) -v -o build/listing.ssd --title STARGLIDER --opt 3 src/main.6502 > $@

# The whole disc played for a long time by a random player, a process a
# seed (tools/soak.mjs): every instruction, write and step watched, and
# anything it finds fails it. SOAK_ALLOW names kinds of what it finds to
# report without failing (split,fresh, say), while one is looked into.
SOAK_SEEDS ?= 1-24
SOAK_SECS  ?= 600
SOAK_JOBS  ?= 12
SOAK_ALLOW ?=
SOAK_ALLOWING = $(if $(SOAK_ALLOW),--allow $(SOAK_ALLOW))
CHECK_SOAK_SEEDS = 1-4
CHECK_SOAK_SECS  = 180
soak: $(TARGET) build/starglider.lst
	node tools/soak.mjs --seeds $(SOAK_SEEDS) --jobs $(SOAK_JOBS) --secs $(SOAK_SECS) $(SOAK_ALLOWING)

# The sound effects on the disc against the ST's YM writes, captured in
# Hatari (make sfxcapture: slow, needs Hatari), and their gates
# (tools/sfxcheck.mjs).
sfx: $(TARGET) build/gen/sfx.json
	node tools/sfxcheck.mjs

# Clare Edgeley's speech on the disc against the levels it packed, timed,
# with a WAV of each clip in build/speech (tools/speechcheck.mjs).
speech: $(TARGET) build/gen/speech.json
	node tools/speechcheck.mjs

sfxcapture:
	$(PYTHON) -I tools/st_sfx.py run tests/st/sfx_all.txt build/sfx/all \
	    --disk "$(ST_STX)" --hatari $(HATARI) --tos $(HATARI_TOS)

# The title song's two candidates as the SN76489 would play them, for
# choosing by ear (decision 5, docs/research/song.md): the ST's sample at
# 4,096 and 6,144 Hz and David Lowe's AY tune from the Spectrum 128K, as
# WAVs in build/song/wav, with the ST's own in build/song/st/star.wav.
song: build/zx/song.json $(PRG) tools/mksong.py tools/mkspeech.py tools/songwav.mjs
	$(PYTHON) -I tools/mksong.py $(PRG) build/zx/song.json build/song
	$(PYTHON) -I tools/st_samples.py $(PRG) --wav build/song/st > /dev/null
	node tools/songwav.mjs build/song

# The title song on the disc (decision 5) against the Spectrum 128K's player
# and mksong.py's zx_bass conversion of it, tick by tick and edge by edge
# (tools/songcheck.mjs, on tools/songmodel.py's model of it), and rendered
# as the chip plays it against the model's render (tools/songcompare.py).
tune: $(TARGET) build/tune/model.json build/song/wav/zx_bass_chip.wav
	node tools/songcheck.mjs
	node tools/songwav.mjs build/tune disc
	$(PYTHON) -I tools/songcompare.py build/tune/wav/disc_chip.wav build/song/wav/zx_bass_chip.wav --min 0.99

build/tune/model.json: build/zx/song.json tools/songmodel.py tools/mksong.py
	$(PYTHON) -I tools/songmodel.py build/zx/song.json $@

build/song/zx_bass.json: build/zx/song.json $(PRG) tools/mksong.py tools/mkspeech.py
	$(PYTHON) -I tools/mksong.py $(PRG) build/zx/song.json build/song

build/song/wav/zx_bass_chip.wav: build/song/zx_bass.json tools/songwav.mjs
	node tools/songwav.mjs build/song zx_bass

# One pass of the tune's AY writes, from its own player (tools/zx_song.py),
# on the 128K tape's snapshot (docs/research/zx.md, "Loading").
build/zx/song.json: build/zx128.z80 tools/zx_song.py tools/zx.py
	$(PYTHON) -I tools/zx_song.py --snap build/zx128.z80 $@

build/zx128.z80: original/zx/Starglider128.tap
	rm -f $@
	$(PYTHON) -I .venv/bin/tap2sna.py -c machine=128 -c timeout=3000 -s 34048 $< $@

spike: build/spike/SPIKE $(SCENES:%=build/scenes/%/beeb.json)
	@for s in $(SCENES); do \
	    echo "== $$s"; \
	    node tools/scenerun.mjs build/scenes/$$s/beeb.json build/scenes/$$s/run.json > /dev/null && \
	    $(PYTHON) -I tools/scenecheck.py build/scenes/$$s/beeb.json build/scenes/$$s/run.json --tolerance 8 || exit 1; \
	done

# The logic's routines, each on every capture (tools/logicrun.mjs's ROUTINES).
LOGIC    = animate flight keys handlers world world_after world_whole collide message frame_end post mine level newgame step
STEPS    = $(patsubst tests/st/steps_%.txt,%,$(wildcard tests/st/steps_*.txt))

logic: build/spike/SPIKE
	@for s in $(STEPS); do for r in $(LOGIC); do \
	    [ -f build/steps/$$s/steps.json ] || { echo "no build/steps/$$s: make steps"; exit 1; }; \
	    node tools/logicrun.mjs build/steps/$$s/steps.json $$r || exit 1; \
	done; done

# The view's drawing besides the objects (src/view.6502: the gunsight, the
# ground dots, the bolt, the shots) against the ST's on every capture, and
# the shots' formula against the scenes' own lines (tools/viewrun.mjs).
view: build/spike/SPIKE
	node tools/viewrun.mjs $(STEPS:%=build/steps/%/steps.json)
	@for s in $(SCENES); do node tools/viewrun.mjs --scenes build/scenes/$$s/scenes.json || exit 1; done

# The panel on every capture's frames (tools/panelcheck.mjs).
# the rotations against the ST's exact one and the approximation's model
build/rotcases.json: tools/rotcases.py tools/st_render.py $(PRG) | build
	$(PYTHON) -I tools/rotcases.py . $@ > /dev/null

rot: build/spike/SPIKE build/rotcases.json
	node tools/rotcheck.mjs build/rotcases.json

panel: build/spike/SPIKE build/gen/panel.json
	node tools/panelcheck.mjs --quiet $(STEPS:%=build/steps/%/steps.json)

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
