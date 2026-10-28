#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litescope-wave.svg: the LiteScope capture of the CPU instruction bus in litex_sim, for
Use-LiteScope-To-Debug-A-SoC: drawn from doc/diagrams/captures/litescope-ibus.vcd, an excerpt of the
dump.vcd written by `litescope_cli -r simsoc_ibus_stb` (twenty samples around the trigger).

    python3 doc/diagrams/litescope-wave.py   # -> doc/wiki/images/litescope-wave.svg
"""

import os

from litex_diagram import *
from wave import Wave, from_vcd

VCD    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures", "litescope-ibus.vcd")
START  = 1     # The first cycle drawn (the trigger is at cycle 4 of the excerpt).
CYCLES = 14

W, H = 1230, 370

DESC = ("Timing diagram of a LiteScope capture: sys_clk, ibus_cyc, ibus_stb, ibus_adr, ibus_ack and "
        "ibus_dat_r over fourteen cycles. cyc and stb rise together at the trigger, adr holds 0xfd8 "
        "until the first ack two cycles later, then 0xfd9, 0xfda and 0xfdb with one ack each: the CPU "
        "refills a cache line of four words, and dat_r carries each instruction word on its ack.")

def draw(d):
    v = from_vcd(VCD, period=2)
    w = Wave(d, 40, 30, cycles=CYCLES, cycle_w=80, name_w=90)
    w.clock("sys_clk")
    w.bit_samples("ibus_cyc",   v["simsoc_ibus_cyc"],  START)
    w.bit_samples("ibus_stb",   v["simsoc_ibus_stb"],  START)
    w.bus_samples("ibus_adr",   v["simsoc_ibus_adr"],  START)
    w.bit_samples("ibus_ack",   v["simsoc_ibus_ack"],  START)
    w.bus_samples("ibus_dat_r", v["simsoc_ibus_dat_r"], START, fmt="0x{:08x}")
    ww, wh = w.draw()
    d.caption(40 + ww/2, 30 + wh + 45, "The capture, triggered on the rising edge of ibus_stb",
              "the CPU fetches a cache line: four words from 0xfd8, one ack each (from dump.vcd)")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litescope-wave", W, H, "A LiteScope capture of the CPU instruction bus", DESC)
