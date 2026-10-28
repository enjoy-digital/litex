#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-csr-wave.svg: a write and a read on the CSR bus, for the CSR-Bus page: the write takes one
cycle (adr, we, dat_w) and lands in the register on the next edge; the read gives dat_r the cycle
after the address (adr, re). No handshake, fixed latency.

    python3 doc/diagrams/litex-csr-wave.py   # -> doc/wiki/images/litex-csr-wave.svg
"""

from litex_diagram import *
from wave import Wave

W, H = 900, 420

DESC = ("Timing diagram of the CSR bus: sys_clk, adr, we, dat_w, re, dat_r and the register's storage "
        "over ten cycles. At cycle 2 the bridge drives adr=0x04, we=1 and dat_w=0xcafe: one cycle, and "
        "storage becomes 0xcafe at cycle 3. At cycle 5 it drives adr=0x04 and re=1: dat_r carries 0xcafe "
        "during cycle 6, the cycle after the address.")

def draw(d):
    w = Wave(d, 40, 30, cycles=10, cycle_w=70, name_w=80)
    w.clock("sys_clk")
    w.bus("adr",     {2: "0x04",   3: None, 5: "0x04", 6: None})
    w.bit("we",      "0010000000")
    w.bus("dat_w",   {2: "0xcafe", 3: None})
    w.bit("re",      "0000010000")
    w.bus("dat_r",   {6: "0xcafe", 7: None})
    w.bus("storage", {0: "0x0000", 3: "0xcafe"})
    ww, wh = w.draw()
    d.caption(40 + ww/2, 30 + wh + 45, "A write at cycle 2, a read at cycle 5",
              "one cycle per write, two per read (the address, then the data), no handshake")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-csr-wave", W, H, "A CSR write and a CSR read", DESC)
