#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import stream
from litex.soc.cores.spi import SPIMaster

# Common SPI LCD Init Sequences -------------------------------------------------------------------

def get_st7789_init_sequence():
    return [
        (0, 0x01),  # Software reset.
        (0, 0x11),  # Sleep out.
        (0, 0x36), (1, 0x00),  # MADCTL.
        (0, 0x3A), (1, 0x55),  # 16-bit RGB565.
        (0, 0x21),  # Display inversion on.
        (0, 0x29),  # Display on.
    ]

# SPI LCD Control ---------------------------------------------------------------------------------

class SPILCD(LiteXModule):
    """SPI LCD controller with basic panel control signals.

    The core instantiates an SPI master for command/data transfers and exposes
    reset, data/command, and backlight controls. Pixel streaming can be layered
    on top of this control block by board or application-specific modules.
    """
    def __init__(self, pads, sys_clk_freq, spi_clk_freq=20e6, with_pixel_stream=False):
        class _SPIPads:
            pass
        spi_pads = _SPIPads()
        spi_pads.clk  = Signal()
        spi_pads.mosi = Signal()
        spi_pads.miso = Signal()
        spi_pads.cs_n = Signal()

        self.spi = SPIMaster(
            pads         = spi_pads,
            data_width   = 8,
            sys_clk_freq = sys_clk_freq,
            spi_clk_freq = spi_clk_freq,
        )
        self.comb += spi_pads.miso.eq(pads.miso)

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

        if with_pixel_stream:
            self.sink = stream.Endpoint([("data", 16)])
            self.pixel_enable = CSRStorage()
            self.pixel_enabled = self.pixel_enable.storage

            clk_divider = max(2, int(round(sys_clk_freq / spi_clk_freq)))
            clk_counter = Signal(max=max(2, clk_divider//2))
            pixel_clk   = Signal()
            pixel_mosi  = Signal()
            pixel_cs_n  = Signal()

            self.comb += [
                pads.clk.eq(Mux(self.pixel_enabled, pixel_clk,  spi_pads.clk)),
                pads.mosi.eq(Mux(self.pixel_enabled, pixel_mosi, spi_pads.mosi)),
                pads.cs_n.eq(Mux(self.pixel_enabled, pixel_cs_n, spi_pads.cs_n)),
                pixel_cs_n.eq(~self.pixel_enabled),
            ]
            if hasattr(pads, "dc"):
                self.comb += pads.dc.eq(Mux(self.pixel_enabled, 1, self.control.fields.dc))

            pixel_shift = Signal(16)
            pixel_bit   = Signal(max=16)

            pixel_fsm = FSM(reset_state="IDLE")
            self.submodules.pixel_fsm = pixel_fsm
            pixel_fsm.act("IDLE",
                If(self.pixel_enabled & self.sink.valid,
                    NextValue(pixel_shift, self.sink.data),
                    NextValue(pixel_bit, 0),
                    self.sink.ready.eq(1),
                    NextState("SEND"),
                )
            )
            pixel_fsm.act("SEND",
                If(clk_counter == 0,
                    pixel_mosi.eq(Array(pixel_shift)[15 - pixel_bit]),
                    NextValue(pixel_bit, pixel_bit + 1),
                    If(pixel_bit == 15,
                        NextState("IDLE"),
                    ),
                )
            )

            self.sync += [
                If(self.pixel_enabled & (pixel_fsm.ongoing("SEND")),
                    If(clk_counter == (clk_divider//2 - 1),
                        clk_counter.eq(0),
                        pixel_clk.eq(~pixel_clk),
                    ).Else(
                        clk_counter.eq(clk_counter + 1),
                    )
                ).Else(
                    clk_counter.eq(0),
                    pixel_clk.eq(0),
                )
            ]
