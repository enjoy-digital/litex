#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-csr-bus.svg: the CSR bus, for the CSR-Bus page: from the main bus to the banks of each
core, the paging and the registers, and what the same Python declaration generates.

    python3 doc/diagrams/litex-csr-bus.py   # -> doc/wiki/images/litex-csr-bus.svg
"""

from litex_diagram import *

W, H = 1400, 600

DESC = ("The CSR bus of a LiteX SoC. The CSR bridge (Wishbone2CSR or AXILite2CSR) turns accesses to "
        "the csr region of the main bus into CSR bus cycles (adr, re, we, dat_w, dat_r, 8 or 32-bit data, "
        "one write cycle, two read cycles). The CSRBankArray gives every core with registers a bank at "
        "a location of csr_paging bytes (0x800 by default): bank index times paging plus the register "
        "index times 4. A register wider than the bus is split in sub-registers. On the right, what one "
        "CSRStorage/CSRStatus declaration produces: the hardware register, the C accessors in csr.h, the "
        "lines in csr.csv/json/svd, the documentation, the entry in the host tools.")

def draw(d):
    # Left: the bus.
    d.box(40, 60, 300, 140, fill=KEY, lines=[("Main bus", 16, "bold"), ("csr region: 0xf0000000, 64 KiB", 12), ("Wishbone / AXI-Lite", 12)])
    d.arrow([(170, 140), (170, 180)], double=True, thick=True)
    d.box(40, 180, 300, 250, lines=[("CSR bridge", 16, "bold"), ("Wishbone2CSR / AXILite2CSR", 12), ("add_csr_bridge(), automatic", 12)])
    d.arrow([(170, 250), (170, 290)], double=True, thick=True)
    d.box(40, 290, 300, 370, fill=GROUP, lines=[("CSR bus", 16, "bold"), ("adr · re · we · dat_w · dat_r", 12), ("csr_data_width 8 / 32 · 14-bit address", 12), ("1 cycle write, 2 cycles read", 12)])
    d.arrow([(300, 330), (360, 330)], double=True, thick=True)

    # Middle: banks.
    d.box(360, 60, 900, 490, fill=FPGA, c=22)
    d.text(630, 90, "CSRBankArray: one bank per core, csr_paging = 0x800", 15, weight="bold")
    d.text(630, 108, "address = csr_base + location × paging + register index × 4", 12, style="italic")
    banks = [("ctrl", 0, [("reset", "0x0"), ("scratch", "0x4"), ("bus_errors", "0x8")]),
             ("uart", 2, [("rxtx", "0x1000"), ("txfull", "0x1004"), ("ev_pending", "0x1010"), ("ev_enable", "0x1014")]),
             ("timer0", 3, [("load", "0x1800"), ("reload", "0x1804"), ("value", "0x1810"), ("uptime_cycles (64-bit: 2 sub-regs)", "0x1820")]),
             ("leds", 5, [("out", "0x2800")])]
    y = 125
    for name, loc, regs in banks:
        h = 24 + 16*len(regs)
        d.box(380, y, 880, y + h, fill=WHITE, c=10)
        d.text(392, y + 17, f"{name}  (location {loc})", 13, anchor="start", weight="bold")
        for i, (r, a) in enumerate(regs):
            d.text(560, y + 17 + 16*(i), f"{name}_{r}", 11, anchor="start")
            d.text(868, y + 17 + 16*(i), a, 11, anchor="end")
        y += h + 10
    d.text(630, 472, "soc.csr.add(\"uart\", n=2) pins a location · 32 locations by default (--csr-address-width)", 11, style="italic")

    # Right: from the declaration.
    d.box(940, 60, 1360, 140, fill=KEY, lines=[("self.scratch = CSRStorage(32, reset=0x12345678,", 12, "bold"), ("    description=\"Scratch register.\")", 12, "bold"), ("in any LiteXModule (AutoCSR)", 11)])
    outs = [("Gateware", "a 32-bit register on the CSR bus, .storage / .wr_stb to the logic"),
            ("csr.h", "ctrl_scratch_read() / ctrl_scratch_write(v), CSR_CTRL_SCRATCH_ADDR"),
            ("csr.csv / json / svd", "csr_register,ctrl_scratch,0xf0000004,1,rw + fields and values"),
            ("Host tools", "bus.regs.ctrl_scratch.read(), litex_cli --regs, LiteScope"),
            ("Documentation", "the register page with its fields (--doc, Sphinx)")]
    y = 170
    for t, s in outs:
        d.box(940, y, 1360, y + 50, lines=[(t, 13, "bold"), (s, 11)])
        y += 60
    d.arrow([(1150, 140), (1150, 170)], thick=True)

    d.caption(700, 525, "One declaration, every view of the register", "CSRStorage (software writes, logic reads) · CSRStatus (logic writes, software reads) · CSRField for bit fields · EventManager for interrupts")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-csr-bus", W, H, "The LiteX CSR bus", DESC)
