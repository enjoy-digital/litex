#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-sim-boot.svg: what litex_sim prints, for SoC-Simulator and Create-A-minimal-SoC: the
build, the BIOS banner, the SoC summary and the prompt. Capture: doc/diagrams/captures/litex-sim-boot.txt.

    python3 doc/diagrams/litex-sim-boot.py   # -> doc/wiki/images/litex-sim-boot.svg
"""

from litex_diagram import *
from terminal import Terminal, capture

NAME  = "litex-sim-boot"
LINES = capture(NAME)
COLS  = Terminal.fit(LINES)
TITLE, SUBTITLE = ("A SoC in Verilator, no board needed",
                   "litex_sim builds the SoC, the BIOS boots and waits at its prompt")
W, H  = Terminal.size(LINES, cols=COLS, caption=(TITLE, SUBTITLE))

DESC = ("A terminal running litex_sim: Verilator builds the SoC, then the LiteX BIOS prints its banner, "
        "the build information, the SoC summary (CPU, bus, CSR width, ROM and SRAM sizes), tries the "
        "boot methods and waits at its litex> prompt.")

def draw(d):
    w, h = Terminal(d, cols=COLS).draw_centered(W, 24, LINES)
    d.caption(W/2, 24 + h + 48, TITLE, SUBTITLE)
    d.footer()

if __name__ == "__main__":
    cli(draw, NAME, W, H, "litex_sim: the BIOS boots in the terminal", DESC)
