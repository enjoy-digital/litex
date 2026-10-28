#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-gdb-session.svg: OpenOCD on the JTAG TAP of a VexRiscv-SMP and a GDB session breaking in the
demo firmware, for Debug-With-GDB. Capture: doc/diagrams/captures/litex-gdb-session.txt (a real session
against litex_sim --with-jtagremote; the "..." is the moment `donut` is typed in the demo console).

    python3 doc/diagrams/litex-gdb-session.py   # -> doc/wiki/images/litex-gdb-session.svg
"""

from litex_diagram import *
from terminal import Terminal, capture, PROMPTS

NAME  = "litex-gdb-session"
LINES = capture(NAME)
W, H  = Terminal.size(LINES)

DESC = ("A terminal: OpenOCD finds the RISC-V TAP (0x10003fff), examines one hart and listens on port 3333; "
        "gdb-multiarch connects to it, shows the CPU halted in readchar_nonblock, sets a breakpoint on donut, "
        "continues, and stops in donut() at donut.c line 26 when the command is typed in the demo console; "
        "the backtrace goes donut, donut_cmd, console_service, main.")

def draw(d):
    w, h = Terminal(d).draw(24, 24, LINES, prompts=PROMPTS + ("(gdb) ",))
    d.caption(24 + w/2, 24 + h + 48, "A breakpoint in the firmware",
              "the CPU stops in donut() when the command is typed in the console")
    d.footer()

if __name__ == "__main__":
    cli(draw, NAME, W, H, "GDB stops the CPU in the demo firmware", DESC)
