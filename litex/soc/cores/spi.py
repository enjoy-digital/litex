#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *

# SPI Master ---------------------------------------------------------------------------------------

class SPIMaster(Module, AutoCSR):
    """4-wire SPI Master

    Provides a simple and minimal hardware SPI Master with CPOL=0, CPHA=0 and build time
    configurable data_width and frequency.
    """
    pads_layout = [("clk", 1), ("cs_n", 1), ("mosi", 1), ("miso", 1)]
    def __init__(self, pads, data_width, sys_clk_freq, spi_clk_freq, with_csr=True, mode="raw"):
        assert mode in ["raw", "aligned"]
        if pads is None:
            pads = Record(self.pads_layout)
        if not hasattr(pads, "cs_n"):
            pads.cs_n = Signal()
        self.pads       = pads
        self.data_width = data_width

        self.start       = Signal()
        self.length      = Signal(8)
        self.done        = Signal()
        self.irq         = Signal()
        self.mosi        = Signal(data_width)
        self.miso        = Signal(data_width)
        self.cs          = Signal(len(pads.cs_n), reset=1)
        self.loopback    = Signal()
        self.clk_divider = Signal(16, reset=math.ceil(sys_clk_freq/spi_clk_freq))

        if with_csr:
            self.add_csr()

        # # #

        clk_enable = Signal()
        cs_enable  = Signal()
        count      = Signal(max=data_width)
        mosi_latch = Signal()
        miso_latch = Signal()

        # Clock generation -------------------------------------------------------------------------
        clk_divider = Signal(16)
        clk_rise    = Signal()
        clk_fall    = Signal()
        self.comb += clk_rise.eq(clk_divider == (self.clk_divider[1:] - 1))
        self.comb += clk_fall.eq(clk_divider == (self.clk_divider     - 1))
        self.sync += [
            clk_divider.eq(clk_divider + 1),
            If(clk_rise,
                pads.clk.eq(clk_enable),
            ).Elif(clk_fall,
                clk_divider.eq(0),
                pads.clk.eq(0),
            )
        ]

        # Control FSM ------------------------------------------------------------------------------
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            self.done.eq(1),
            If(self.start,
                self.done.eq(0),
                mosi_latch.eq(1),
                NextState("START")
            )
        )
        fsm.act("START",
            NextValue(count, 0),
            If(clk_fall,
                cs_enable.eq(1),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            clk_enable.eq(1),
            cs_enable.eq(1),
            If(clk_fall,
                NextValue(count, count + 1),
                If(count == (self.length - 1),
                    NextState("STOP")
                )
            )
        )
        fsm.act("STOP",
            cs_enable.eq(1),
            If(clk_rise,
                miso_latch.eq(1),
                self.irq.eq(1),
                NextState("IDLE")
            )
        )

        # Chip Select generation -------------------------------------------------------------------
        if hasattr(pads, "cs_n"):
            for i in range(len(pads.cs_n)):
                self.sync += pads.cs_n[i].eq(~self.cs[i] | ~cs_enable)

        # Master Out Slave In (MOSI) generation (generated on spi_clk falling edge) ----------------
        mosi_data  = Signal(data_width)
        mosi_array = Array(mosi_data[i] for i in range(data_width))
        mosi_sel   = Signal(max=data_width)
        self.sync += [
            If(mosi_latch,
                mosi_data.eq(self.mosi),
                mosi_sel.eq((self.length-1) if mode == "aligned" else (data_width-1)),
            ).Elif(clk_fall,
                If(cs_enable, pads.mosi.eq(mosi_array[mosi_sel])),
                mosi_sel.eq(mosi_sel - 1)
            ),
        ]

        # Master In Slave Out (MISO) capture (captured on spi_clk rising edge) --------------------
        miso      = Signal()
        miso_data = Signal(data_width)
        self.sync += [
            If(clk_rise,
                If(self.loopback,
                    miso_data.eq(Cat(pads.mosi, miso_data))
                ).Else(
                    miso_data.eq(Cat(pads.miso, miso_data))
                )
            )
        ]
        self.sync += If(miso_latch, self.miso.eq(miso_data))

    def add_csr(self, with_cs=True, with_loopback=True):
        self._control  = CSRStorage(fields=[
            CSRField("start",  size=1, offset=0, pulse=True, description="Write ``1`` to start SPI Xfer"),
            CSRField("length", size=8, offset=8, description="SPI Xfer length (in bits).")
        ], description="SPI Control.")
        self._status   = CSRStatus(fields=[
            CSRField("done", size=1, offset=0, description="SPI Xfer done when read as ``1``.")
        ], description="SPI Status.")
        self._mosi     = CSRStorage(self.data_width, reset_less=True, description="SPI MOSI data (MSB-first serialization).")
        self._miso     = CSRStatus(self.data_width,  description="SPI MISO data (MSB-first de-serialization).")
        self.comb += [
            self.start.eq(self._control.fields.start),
            self.length.eq(self._control.fields.length),
            self.mosi.eq(self._mosi.storage),
            self._status.fields.done.eq(self.done),
            self._miso.status.eq(self.miso),
        ]
        if with_cs:
            self._cs       = CSRStorage(fields=[
                CSRField("sel", len(self.cs), reset=1, description="Write ``1`` to corresponding bit to enable Xfer for chip.")
            ], description="SPI Chip Select.")
            self.comb += self.cs.eq(self._cs.storage)
        if with_loopback:
            self._loopback = CSRStorage(description="SPI loopback mode.\n\n Write ``1`` to enable MOSI to MISO internal loopback.")
            self.comb += self.loopback.eq(self._loopback.storage)

    def add_clk_divider(self):
        self._clk_divider = CSRStorage(16, description="SPI Clk Divider.", reset=self.clk_divider.reset)
        self.comb += self.clk_divider.eq(self._clk_divider.storage)

# SPI Slave ----------------------------------------------------------------------------------------

class SPISlave(Module):
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
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
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
