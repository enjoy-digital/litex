#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.soc.interconnect.csr import *

# SPI Slave ----------------------------------------------------------------------------------------

class SPISlave(LiteXModule):
    """4-wire SPI Slave

    Provides a simple and minimal hardware SPI Slave with CPOL=0, CPHA=0 and build time configurable
    data_width.
    """
    pads_layout = [("clk", 1), ("cs_n", 1), ("mosi", 1), ("miso", 1)]
    def __init__(self, pads, data_width):
        if pads is None:
            pads = Record(self.pads_layout)
        if not hasattr(pads, "cs_n"):
            pads.cs_n = Signal()
        self.pads       = pads
        self.data_width = data_width

        self.start    = Signal()            # o, Signal a start of SPI Xfer.
        self.length   = Signal(8)           # o, Signal the length of the SPI Xfer (in bits).
        self.done     = Signal()            # o, Signal that SPI Xfer is done/inactive.
        self.irq      = Signal()            # o, Signal the end of a SPI Xfer.
        self.mosi     = Signal(data_width)  # i, Data to send on SPI MOSI.
        self.miso     = Signal(data_width)  # o, Data received on SPI MISO.
        self.loopback = Signal()            # i, Loopback enable.

        # # #

        clk  = Signal()
        cs   = Signal()
        mosi = Signal()
        miso = Signal()

        # IOs <--> Internal (input resynchronization) ----------------------------------------------
        self.specials += [
            MultiReg(pads.clk,    clk),
            MultiReg(~pads.cs_n,   cs),
            MultiReg(pads.mosi,  mosi),
        ]
        self.comb += pads.miso.eq(miso)

        # Clock detection --------------------------------------------------------------------------
        clk_d    = Signal()
        clk_rise = Signal()
        clk_fall = Signal()
        self.sync += clk_d.eq(clk)
        self.comb += clk_rise.eq(clk & ~clk_d)
        self.comb += clk_fall.eq(~clk & clk_d)

        # Control FSM ------------------------------------------------------------------------------
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(cs,
                self.start.eq(1),
                NextValue(self.length, 0),
                NextState("XFER")
            ).Else(
                self.done.eq(1)
            )
        )
        fsm.act("XFER",
            If(~cs,
                self.irq.eq(1),
                NextState("IDLE")
            ),
            NextValue(self.length, self.length + clk_rise)
        )

        # Master In Slave Out (MISO) generation (generated on spi_clk falling edge) ----------------
        miso_data = Signal(data_width)
        self.sync += [
            If(self.start,
                miso_data.eq(self.miso)
            ).Elif(cs & clk_fall,
                miso_data.eq(Cat(Signal(), miso_data[:-1]))
            )
        ]
        self.comb += [
            If(self.loopback,
                miso.eq(mosi)
            ).Else(
                miso.eq(miso_data[-1]),
            )
        ]

        # Master Out Slave In (MOSI) capture (captured on spi_clk rising edge) ---------------------
        self.sync += [
            If(cs & clk_rise,
                self.mosi.eq(Cat(mosi, self.mosi[:-1]))
            )
        ]
