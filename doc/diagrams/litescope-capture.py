#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litescope-capture.svg: litescope_cli: list, trigger, capture. Capture: doc/diagrams/captures/litescope-capture.txt (a real session against litex_sim).

    python3 doc/diagrams/litescope-capture.py   # -> doc/wiki/images/litescope-capture.svg
"""

from litex_diagram import *
from terminal import Terminal, capture, PROMPTS

NAME  = "litescope-capture"
LINES = capture(NAME)
COLS  = Terminal.fit(LINES)
TITLE, SUBTITLE = ("A capture with litescope_cli",
                   "list the signals, arm a trigger, the samples land in dump.vcd for GTKWave")
W, H  = Terminal.size(LINES, cols=COLS, caption=(TITLE, SUBTITLE))

DESC = ("A terminal: litescope_cli --list prints the signals of the analyzer (the CPU instruction and data buses), litescope_cli -r simsoc_ibus_stb arms a rising-edge trigger, waits, uploads 508 words and writes dump.vcd, opened with gtkwave.")

def draw(d):
    w, h = Terminal(d, cols=COLS).draw_centered(W, 24, LINES, prompts=PROMPTS)
    d.caption(W/2, 24 + h + 48, TITLE, SUBTITLE)
    d.footer()

if __name__ == "__main__":
    cli(draw, NAME, W, H, "litescope_cli: list, trigger, capture", DESC)
