#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-cli-regs.svg: litex_cli and RemoteClient through a host bridge. Capture: doc/diagrams/captures/litex-cli-regs.txt (a real session against litex_sim).

    python3 doc/diagrams/litex-cli-regs.py   # -> doc/wiki/images/litex-cli-regs.svg
"""

from litex_diagram import *
from terminal import Terminal, capture, PROMPTS

NAME  = "litex-cli-regs"
LINES = capture(NAME)
COLS  = Terminal.fit(LINES)
TITLE, SUBTITLE = ("The SoC, driven from the host",
                   "litex_cli, a script and the console, through one litex_server")
W, H  = Terminal.size(LINES, cols=COLS, caption=(TITLE, SUBTITLE))

DESC = ("A terminal: litex_server on the serial port, litex_cli --ident prints the SoC identifier, --regs --filter ctrl lists the three ctrl registers, a write and a read of ctrl_scratch, a Python script using RemoteClient, then litex_term crossover showing the BIOS console and its mem_list through the same bridge.")

def draw(d):
    w, h = Terminal(d, cols=COLS).draw_centered(W, 24, LINES, prompts=PROMPTS)
    d.caption(W/2, 24 + h + 48, TITLE, SUBTITLE)
    d.footer()

if __name__ == "__main__":
    cli(draw, NAME, W, H, "litex_cli and RemoteClient through a host bridge", DESC)
