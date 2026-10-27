#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-core-anatomy.svg: what a LiteX core is made of and what the SoC derives from it, for the
Add-A-New-Core and Cores pages.

    python3 doc/diagrams/litex-core-anatomy.py   # -> doc/wiki/images/litex-core-anatomy.svg
"""

from litex_diagram import *

W, H = 1400, 600

DESC = ("Anatomy of a LiteX core. A LiteXModule with, on its control side, CSRStorage and CSRStatus "
        "registers (with fields and descriptions) collected by AutoCSR, and an EventManager for the "
        "interrupts; on its data side, stream sink/source endpoints and optionally a Wishbone or AXI "
        "master (a DMA) or slave (a memory-mapped region); pads to the FPGA I/Os through the generic "
        "specials; its logic in sys or another clock domain. From the same class the SoC derives the "
        "location on the CSR bus, the interrupt line, the csr.h accessors, the csr.csv/json/svd "
        "entries, the host tools' view and the documentation.")

def draw(d):
    # The core.
    d.box(420, 60, 980, 470, fill=FPGA, c=22)
    d.text(700, 90, "class MyCore(LiteXModule)", 18, weight="bold")
    d.text(700, 110, "Module + AutoCSR + AutoDoc · litex/soc/cores/<name>.py or your project", 12, style="italic")
    d.box(440, 130, 700, 215, lines=[("Streams", 14, "bold"), ("self.sink / self.source", 11), ("valid · ready · first · last · payload", 11)])
    d.box(700, 130, 960, 215, lines=[("Bus interface (optional)", 14, "bold"), ("wishbone / AXI master: a DMA", 11), ("or slave: a memory-mapped region", 11)])
    d.box(440, 235, 700, 320, fill=KEY, lines=[("CSRs", 14, "bold"), ("CSRStorage: software writes", 11), ("CSRStatus: logic writes", 11), ("CSRField · description", 11)])
    d.box(700, 235, 960, 320, fill=KEY, lines=[("EventManager", 14, "bold"), ("EventSourcePulse / Process / Level", 11), ("status · pending · enable", 11), ("irq", 11)])
    d.box(440, 340, 960, 450, fill=WHITE, lines=[("The logic", 14, "bold"), ("self.comb / self.sync (or self.sync.<cd>), FSMs, submodules", 11), ("pads = platform.request(\"...\"): I/Os through the generic specials (DDR, differential, tristate)", 11), ("# # # separates the interface from the implementation", 11)])

    # Left: the SoC side.
    d.box(40, 130, 360, 215, fill=GROUP, lines=[("Main bus · other cores", 14, "bold"), ("bus.add_master / add_slave", 11), ("source.connect(other.sink)", 11)])
    d.box(40, 235, 360, 320, fill=GROUP, lines=[("CSR bus", 14, "bold"), ("a location (csr_paging) per core", 11), ("one bank, registers in order", 11)])
    d.box(40, 340, 360, 450, fill=GROUP, lines=[("IRQ handler", 14, "bold"), ("soc.irq.add(\"mycore\")", 11), ("<MYCORE>_INTERRUPT in soc.h", 11)])
    d.arrow([(360, 172), (440, 172)], double=True, thick=True)
    d.arrow([(360, 277), (440, 277)], double=True)
    d.arrow([(830, 320), (830, 330), (400, 330), (400, 395), (360, 395)])
    d.text(383, 362, "irq", 11, anchor="end", style="italic")

    # Right: what is generated.
    d.text(1200, 100, "From the same declaration", 15, weight="bold", style="italic")
    outs = [("csr.h", "mycore_<reg>_read() / _write(), fields"),
            ("csr.csv · csr.json · csr.svd", "addresses for the tools, Rust, DTS"),
            ("Host tools", "bus.regs.mycore_<reg>, litex_cli, LiteScope"),
            ("Documentation", "--doc: registers, fields, ModuleDoc"),
            ("The SoC map", "location, interrupt, region, constants")]
    y = 120
    ys = []
    for t, s in outs:
        d.box(1040, y, 1360, y + 55, lines=[(t, 13, "bold"), (s, 11)])
        ys.append(y + 27)
        y += 66
    d.line(980, 277, 1010, 277, col=THICK, w=4)
    d.line(1010, ys[0], 1010, ys[-1], col=THICK, w=4)
    for yc in ys:
        d.arrow([(1010, yc), (1040, yc)])

    d.caption(700, 525, "self.mycore = MyCore(pads): the rest is derived", "attribute name = core name everywhere: mycore location, mycore_* registers, MYCORE_INTERRUPT")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-core-anatomy", W, H, "Anatomy of a LiteX core", DESC)
