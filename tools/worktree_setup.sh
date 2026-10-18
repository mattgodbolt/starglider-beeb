#!/bin/sh
# Ready a git worktree of this repository to build and check, from the
# main checkout's untracked inputs: links to the originals and the Python
# and Node environments, copies of the ST's program, of each captured
# scene as the port's inputs (the captures themselves linked, read-only)
# and of the logic's captures, and local.mk naming the main checkout's
# baron.
#
#   tools/worktree_setup.sh MAIN        run from the worktree's top
set -e
main=$(cd "$1" && pwd)
for d in .venv node_modules; do [ -e "$d" ] || ln -s "$main/$d" "$d"; done
for f in "$main"/original/*; do [ -e "original/$(basename "$f")" ] || ln -s "$f" original/; done
mkdir -p build/st build/scenes
cp -a "$main/build/st/." build/st/
for s in "$main"/build/scenes/*/; do
    n=$(basename "$s")
    mkdir -p "build/scenes/$n"
    ln -sf "$s/scenes.json" "build/scenes/$n/scenes.json"
    cp "$s/beeb.json" "build/scenes/$n/beeb.json"
done
# newer than what they're made from, so make doesn't make them again
touch build/scenes/*/beeb.json
# the logic's captures (tools/st_steps.py), copied: an agent may add its own
for s in "$main"/build/steps/*/; do
    [ -f "$s/steps.json" ] || continue
    n=$(basename "$s")
    mkdir -p "build/steps/$n"
    cp "$s/steps.json" "build/steps/$n/steps.json"
done
echo "BARON := $(cd "$main/.." && pwd)/baron/build/src/baron" > local.mk
echo "ready: make check, make spike, make memory"
