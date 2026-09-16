#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *
from litex.soc.cores.spi import SPIMaster

# SPI LCD Control ---------------------------------------------------------------------------------

class SPILCD(LiteXModule):
    """SPI LCD controller with basic panel control signals.

    The core instantiates an SPI master for command/data transfers and exposes
    reset, data/command, and backlight controls. Pixel streaming can be layered
    on top of this control block by board or application-specific modules.
    """
    def __init__(self, pads, sys_clk_freq, spi_clk_freq=20e6):
        self.spi = SPIMaster(
            pads         = pads,
            data_width   = 8,
            sys_clk_freq = sys_clk_freq,
            spi_clk_freq = spi_clk_freq,
        )

        self.control = CSRStorage(fields=[
            CSRField("reset",     size=1, offset=0, description="LCD Reset (active low on rst_n pad)."),
            CSRField("dc",        size=1, offset=1, description="LCD Data/Command selection."),
            CSRField("backlight", size=1, offset=2, description="LCD Backlight Enable."),
        ])

        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(~self.control.fields.reset)
        if hasattr(pads, "dc"):
            self.comb += pads.dc.eq(self.control.fields.dc)
        if hasattr(pads, "backlight"):
            self.comb += pads.backlight.eq(self.control.fields.backlight)
