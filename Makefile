# STARGLIDER — BBC Master 128 port
#
#   make fetch    download every version of the original into original/
#   make venv     the Python tools' environment (.venv: SkoolKit, Capstone,
#                 Pillow, NumPy)

PYTHON  ?= .venv/bin/python

# A failed step leaves no half-made target behind.
.DELETE_ON_ERROR:

.PHONY: fetch venv

fetch:
	tools/fetch_original.sh

venv:
	uv sync
