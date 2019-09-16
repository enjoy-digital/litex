# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

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
    def __init__(self, pads, data_width, sys_clk_freq, spi_clk_freq, with_csr=True):
        if pads is None:
            pads = Record(self.pads_layout)
        if not hasattr(pads, "cs_n"):
            pads.cs_n = Signal()
        self.pads       = pads
        self.data_width = data_width

        self.start    = Signal()
        self.length   = Signal(8)
        self.done     = Signal()
        self.irq      = Signal()
        self.mosi     = Signal(data_width)
        self.miso     = Signal(data_width)
        self.cs       = Signal(len(pads.cs_n), reset=1)
        self.loopback = Signal()

        if with_csr:
            self.add_csr()

        # # #

        bits  = Signal(8)
        xfer  = Signal()
        shift = Signal()

        # Clock generation -------------------------------------------------------------------------
        clk_divide  = math.ceil(sys_clk_freq/spi_clk_freq)
        clk_divider = Signal(max=clk_divide)
        clk_rise    = Signal()
        clk_fall    = Signal()
        self.sync += [
            If(clk_rise, pads.clk.eq(xfer)),
            If(clk_fall, pads.clk.eq(0)),
            If(clk_fall,
                clk_divider.eq(0)
            ).Else(
                clk_divider.eq(clk_divider + 1)
            )
        ]
        self.comb += clk_rise.eq(clk_divider == (clk_divide//2 - 1))
        self.comb += clk_fall.eq(clk_divider == (clk_divide - 1))

        # Control FSM ------------------------------------------------------------------------------
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            self.done.eq(1),
            If(self.start,
                NextValue(bits, 0),
                NextState("WAIT-CLK-FALL")
            )
        )
        fsm.act("WAIT-CLK-FALL",
            If(clk_fall,
                NextState("XFER")
            )
        )
        fsm.act("XFER",
            If(bits == self.length,
                NextState("END")
            ).Elif(clk_fall,
                NextValue(bits, bits + 1)
            ),
            xfer.eq(1),
            shift.eq(1)
        )
        fsm.act("END",
            If(clk_rise,
                NextState("IDLE")
            ),
            shift.eq(1),
            self.irq.eq(1)
        )

        # Chip Select generation -------------------------------------------------------------------
        if hasattr(pads, "cs_n"):
            for i in range(len(pads.cs_n)):
                self.comb += pads.cs_n[i].eq(~self.cs[i] | ~xfer)

        # Master Out Slave In (MOSI) generation (generated on spi_clk falling edge) ---------------
        mosi_data = Signal(data_width)
        self.sync += \
            If(self.start,
                mosi_data.eq(self.mosi)
            ).Elif(clk_rise & shift,
                mosi_data.eq(Cat(Signal(), mosi_data[:-1]))
            ).Elif(clk_fall,
                pads.mosi.eq(mosi_data[-1])
            )

        # Master In Slave Out (MISO) capture (captured on spi_clk rising edge) --------------------
        miso      = Signal()
        miso_data = self.miso
        self.sync += \
            If(shift,
                If(clk_rise,
                    If(self.loopback,
                        miso.eq(pads.mosi)
                    ).Else(
                        miso.eq(pads.miso)
                    )
                ).Elif(clk_fall,
                    miso_data.eq(Cat(miso, miso_data[:-1]))
                )
            )

    def add_csr(self):
        self._control  = CSRStorage(fields=[
            CSRField("start",  size=1, offset=0, pulse=True),
            CSRField("length", size=8, offset=8)])
        self._status   = CSRStatus(fields=[
            CSRField("done", size=1, offset=0)])
        self._mosi     = CSRStorage(self.data_width)
        self._miso     = CSRStatus(self.data_width)
        self._cs       = CSRStorage(len(self.cs), reset=1)
        self._loopback = CSRStorage()

        self.comb += [
            self.start.eq(self._control.fields.start),
            self.length.eq(self._control.fields.length),
            self.mosi.eq(self._mosi.storage),
            self.cs.eq(self._cs.storage),
            self.loopback.eq(self._loopback.storage),

            self._status.fields.done.eq(self.done),
            self._miso.status.eq(self.miso),
        ]

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

        self.start    = Signal()
        self.length   = Signal(8)
        self.done     = Signal()
        self.irq      = Signal()
        self.mosi     = Signal(data_width)
        self.miso     = Signal(data_width)
        self.cs       = Signal()
        self.loopback = Signal()

        # # #

        clk  = Signal()
        cs   = Signal()
        mosi = Signal()
        miso = Signal()

        # IOs <--> Internal (input resynchronization) ----------------------------------------------
        self.specials += [
            MultiReg(pads.clk, clk),
            MultiReg(~pads.cs_n, cs),
            MultiReg(pads.mosi, mosi),
        ]
        self.comb += pads.miso.eq(miso)

        # Clock detection --------------------------------------------------------------------------
        clk_d = Signal()
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
        self.sync += \
            If(self.start,
                miso_data.eq(self.miso)
            ).Elif(cs & clk_fall,
                miso_data.eq(Cat(Signal(), miso_data[:-1]))
            )
        self.comb += \
            If(self.loopback,
                miso.eq(mosi)
            ).Else(
                miso.eq(miso_data[-1]),
            )

        # Master Out Slave In (MOSI) capture (captured on spi_clk rising edge) ---------------------
        self.sync += \
            If(cs & clk_rise,
                self.mosi.eq(Cat(mosi, self.mosi[:-1]))
            )
