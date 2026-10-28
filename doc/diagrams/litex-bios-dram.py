#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-bios-dram.svg: the BIOS initializing a DRAM, for the BIOS page: the SoC summary with the
SDRAM line, the controller switched to hardware control, the memtest and the memspeed, then the boot
sequence and the prompt. Capture: doc/diagrams/captures/litex-bios-dram.txt (litex_sim --with-sdram).

    python3 doc/diagrams/litex-bios-dram.py   # -> doc/wiki/images/litex-bios-dram.svg
"""

from litex_diagram import *
from terminal import Terminal, capture

NAME  = "litex-bios-dram"
LINES = capture(NAME)
COLS  = Terminal.fit(LINES)
TITLE, SUBTITLE = ("The BIOS brings up a DRAM, then boots",
                   "initialization, memtest and memspeed come before the boot methods")
W, H  = Terminal.size(LINES, cols=COLS, caption=(TITLE, SUBTITLE))

DESC = ("A terminal running litex_sim --with-sdram: the BIOS summary lists the CPU, the bus, the CSR width, "
        "the ROM, the SRAM, the L2 cache and a 64 MiB SDRAM; the initialization switches the SDRAM to software "
        "then hardware control, runs a memtest (OK) and a memspeed; the boot tries the serial port, times out, "
        "finds no boot medium and drops to the litex> prompt.")

def draw(d):
    w, h = Terminal(d, cols=COLS).draw_centered(W, 24, LINES)
    d.caption(W/2, 24 + h + 48, TITLE, SUBTITLE)
    d.footer()

if __name__ == "__main__":
    cli(draw, NAME, W, H, "The BIOS initializing the SDRAM", DESC)
