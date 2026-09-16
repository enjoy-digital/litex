#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from litex.soc.cores.i2c import I2CMaster

# OV5640 Camera Control ----------------------------------------------------------------------------

class OV5640Camera(LiteXModule):
    """OV5640 DVP camera control block.

    Provides SCCB/I2C control, reset/power controls, and XCLK generation.
    Pixel capture can be connected on top of this control block.
    """
    def __init__(self, pads, sys_clk_freq, xclk_freq=24e6, with_capture=True):
        self.i2c = I2CMaster(pads)

        self.control = CSRStorage(fields=[
            CSRField("reset",  size=1, offset=0, description="Camera reset."),
            CSRField("power",  size=1, offset=1, description="Camera power-down."),
            CSRField("enable", size=1, offset=2, description="Camera XCLK enable."),
        ])

        # XCLK generation.
        divider = max(2, int(round(sys_clk_freq / xclk_freq)))
        xclk_counter = Signal(max=max(2, divider//2))
        xclk         = Signal()
        self.sync += If(self.control.fields.enable,
            If(xclk_counter == (divider//2 - 1),
                xclk_counter.eq(0),
                xclk.eq(~xclk),
            ).Else(
                xclk_counter.eq(xclk_counter + 1),
            )
        ).Else(
            xclk_counter.eq(0),
            xclk.eq(0),
        )

        if hasattr(pads, "xclk"):
            self.comb += pads.xclk.eq(xclk)
        if hasattr(pads, "pwdn"):
            self.comb += pads.pwdn.eq(self.control.fields.power)
        if hasattr(pads, "rst_n"):
            self.comb += pads.rst_n.eq(~self.control.fields.reset)

        # DVP capture path.
        if with_capture and all(hasattr(pads, name) for name in ["pclk", "href", "vsync", "data"]):
            self.cd_pclk = ClockDomain()
            self.comb += self.cd_pclk.clk.eq(pads.pclk)
            self.comb += self.cd_pclk.rst.eq(self.control.fields.reset)

            self.pclk_source = stream.Endpoint([("data", 8)])
            capture_fsm = ClockDomainsRenamer("pclk")(FSM(reset_state="IDLE"))
            self.submodules.capture_fsm = capture_fsm
            capture_fsm.act("IDLE",
                If(pads.vsync,
                    NextState("FRAME"),
                )
            )
            capture_fsm.act("FRAME",
                If(pads.href,
                    self.pclk_source.valid.eq(1),
                    self.pclk_source.data.eq(pads.data),
                ),
                If(~pads.vsync,
                    NextState("IDLE"),
                )
            )

            self.capture_cdc = stream.ClockDomainCrossing(
                layout = [("data", 8)],
                cd_from = "pclk",
                cd_to   = "sys",
            )
            self.comb += self.pclk_source.connect(self.capture_cdc.sink)
            self.source = self.capture_cdc.source
