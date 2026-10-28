#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-wishbone-wave.svg: a single write and a single read on a Wishbone classic bus, for the
Wishbone-Bus page: the master raises cyc and stb with the address and the data, the slave answers
with ack (the next cycle here, a wait state on the read), one word per ack, nothing outstanding.

    python3 doc/diagrams/litex-wishbone-wave.py   # -> doc/wiki/images/litex-wishbone-wave.svg
"""

from litex_diagram import *
from wave import Wave

W, H = 900, 440

DESC = ("Timing diagram of a Wishbone write and read: sys_clk, cyc, stb, we, adr, dat_w, ack and dat_r "
        "over ten cycles. Cycles 1 and 2: the master holds cyc, stb, we, adr=0x04 and dat_w=0xcafe until "
        "the slave's ack at cycle 2. Cycles 4 to 6: cyc and stb with we low and adr=0x04; the slave "
        "inserts a wait state and acks at cycle 6 with dat_r=0xcafe. The bus is idle in between.")

def draw(d):
    w = Wave(d, 40, 30, cycles=10, cycle_w=70, name_w=80)
    w.clock("sys_clk")
    w.bit("cyc",   "0110111000")
    w.bit("stb",   "0110111000")
    w.bit("we",    "0110000000")
    w.bus("adr",   {1: "0x04", 3: None, 4: "0x04", 7: None})
    w.bus("dat_w", {1: "0xcafe", 3: None})
    w.bit("ack",   "0010001000")
    w.bus("dat_r", {6: "0xcafe", 7: None})
    ww, wh = w.draw()
    d.caption(40 + ww/2, 30 + wh + 45, "A write at cycle 1, a read at cycle 4",
              "the request holds until the ack: one cycle here, a wait state on the read, nothing outstanding")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-wishbone-wave", W, H, "A Wishbone write and a Wishbone read", DESC)
