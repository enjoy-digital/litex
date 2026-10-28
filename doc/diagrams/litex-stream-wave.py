#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-stream-wave.svg: a four-word packet on a LiteX stream, for the Streams page: a word moves on
every cycle with valid and ready both high; the sink stalls one cycle (ready low) and the source
holds its word; first marks the first word, last the last one.

    python3 doc/diagrams/litex-stream-wave.py   # -> doc/wiki/images/litex-stream-wave.svg
"""

from litex_diagram import *
from wave import Wave

W, H = 900, 380

DESC = ("Timing diagram of a LiteX stream: sys_clk, valid, ready, first, last and data over eight cycles. "
        "A packet of four words D0 to D3: valid is high from cycle 1 to 5; ready drops at cycle 3, so D2 "
        "presented at cycle 3 is held and transferred at cycle 4; first is high with D0 at cycle 1, last "
        "with D3 at cycle 5. A transfer happens on each cycle where valid and ready are both high.")

def draw(d):
    w = Wave(d, 40, 30, cycles=8, cycle_w=80, name_w=70)
    w.clock("sys_clk")
    w.bit("valid", "01111100")
    w.bit("ready", "11101111")
    w.bit("first", "01000000")
    w.bit("last",  "00000100")
    w.bus("data",  {1: "D0", 2: "D1", 3: "D2", 5: "D3", 6: None})
    ww, wh = w.draw()
    d.caption(40 + ww/2, 30 + wh + 45, "A packet of four words, with a stall",
              "a word moves when valid and ready are both high; D2 waits one cycle for the sink")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-stream-wave", W, H, "A packet on a LiteX stream", DESC)
