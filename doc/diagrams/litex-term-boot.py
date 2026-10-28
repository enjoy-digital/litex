#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-term-boot.svg: litex_term --kernel: the firmware boots. Capture: doc/diagrams/captures/litex-term-boot.txt (a real session against litex_sim).

    python3 doc/diagrams/litex-term-boot.py   # -> doc/wiki/images/litex-term-boot.svg
"""

from litex_diagram import *
from terminal import Terminal, capture, PROMPTS

NAME  = "litex-term-boot"
LINES = capture(NAME)
COLS  = Terminal.fit(LINES)
TITLE, SUBTITLE = ("The demo firmware, booted over serial",
                   "litex_term uploads demo.bin when the BIOS asks for it, then shows its console")
W, H  = Terminal.size(LINES, cols=COLS, caption=(TITLE, SUBTITLE))

DESC = ("A terminal running litex_term with --kernel=demo.bin: the BIOS boots, asks for a serial boot, litex_term uploads demo.bin to 0x40000000 and the device executes it (Liftoff!); the demo prints its command list and answers helloc with Hello, world.")

def draw(d):
    w, h = Terminal(d, cols=COLS).draw_centered(W, 24, LINES, prompts=PROMPTS + ("litex-demo-app> ",))
    d.caption(W/2, 24 + h + 48, TITLE, SUBTITLE)
    d.footer()

if __name__ == "__main__":
    cli(draw, NAME, W, H, "litex_term --kernel: the firmware boots", DESC)
