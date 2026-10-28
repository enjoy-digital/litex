#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-minimal-soc-build.svg: the log of the minimal Arty target built with --no-compile-gateware,
for Create-A-minimal-SoC: the "Finalized SoC" summary (regions, masters, slaves, CSR locations), the
BIOS, the output directory. Capture: doc/diagrams/captures/litex-minimal-soc-build.txt.

    python3 doc/diagrams/litex-minimal-soc-build.py   # -> doc/wiki/images/litex-minimal-soc-build.svg
"""

from litex_diagram import *
from terminal import Terminal, capture

NAME  = "litex-minimal-soc-build"
COLS  = 112
LINES = capture(NAME, cols=COLS)
W, H  = Terminal.size(LINES, cols=COLS)

DESC = ("A terminal running python3 minimal_soc.py --build --no-compile-gateware: the SoC builder prints "
        "the finalized SoC (a 32-bit Wishbone bus with the rom, sram and csr regions, the two CPU bus "
        "masters, the five CSR locations: ctrl, identifier_mem, leds, timer0, uart), the BIOS is compiled "
        "and the ROM resized to it, and build/digilent_arty holds csr.csv, csr.json, gateware, litex.log "
        "and software.")

def draw(d):
    w, h = Terminal(d, cols=COLS).draw(24, 24, LINES)
    d.caption(24 + w/2, 24 + h + 48, "The SoC, built without the FPGA toolchain",
              "the builder prints the memory map and the CSR locations, compiles the BIOS and writes build/")
    d.footer()

if __name__ == "__main__":
    cli(draw, NAME, W, H, "The minimal SoC built with --no-compile-gateware", DESC)
