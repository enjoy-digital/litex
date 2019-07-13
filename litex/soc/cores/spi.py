# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import math

from migen import *

from litex.soc.interconnect.csr import *

# SPI Master ---------------------------------------------------------------------------------------

SPI_CONTROL_START  = 0
SPI_CONTROL_LENGTH = 8

SPI_STATUS_DONE = 0

class SPIMaster(Module, AutoCSR):
    """4-wire SPI Master

    Provides a simple and minimal hardware SPI Master with CPOL=0, CPHA=0 and build time
    configurable data_width and frequency.
    """
    pads_layout = [("clk", 1), ("cs_n", 1), ("mosi", 1), ("miso", 1)]
    def __init__(self, pads, data_width, sys_clk_freq, spi_clk_freq, with_control=True):
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

        if with_control:
            self.add_control()

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
                    miso.eq(pads.miso),
                ).Elif(clk_fall,
                    miso_data.eq(Cat(miso, miso_data[:-1]))
                )
            )

        # Loopback ---------------------------------------------------------------------------------
        self.comb += If(self.loopback, pads.miso.eq(pads.mosi))

    def add_control(self):
        self._control  = CSRStorage(16)
        self._status   = CSRStatus()
        self._mosi     = CSRStorage(self.data_width)
        self._miso     = CSRStatus(self.data_width)
        self._cs       = CSRStorage(len(self.cs), reset=1)
        self._loopback = CSRStorage()

        self.comb += [
            self.start.eq(self._control.re & self._control.storage[SPI_CONTROL_START]),
            self.length.eq(self._control.storage[SPI_CONTROL_LENGTH:]),
            self.mosi.eq(self._mosi.storage),
            self.cs.eq(self._cs.storage),
            self.loopback.eq(self._loopback.storage),

            self._status.status[SPI_STATUS_DONE].eq(self.done),
            self._miso.status.eq(self.miso),
        ]
