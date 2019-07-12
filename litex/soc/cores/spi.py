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
    def __init__(self, pads, data_width, sys_clk_freq, spi_clk_freq):
        if pads is None:
            pads = Record(self.pads_layout)
        self.pads = pads

        self._control = CSRStorage(16)
        self._status  = CSRStatus(1)
        self._mosi    = CSRStorage(data_width)
        self._miso    = CSRStatus(data_width)
        if hasattr(pads, "cs_n"):
            self._cs      = CSRStorage(len(pads.cs_n), reset=1)

        self.irq = Signal()

        # # #

        bits  = Signal(8)
        cs    = Signal()
        shift = Signal()

        # Control/Status ---------------------------------------------------------------------------
        start  = Signal()
        length = Signal(8)
        done   = Signal()

        # XFER start: initialize SPI XFER on SPI_CONTROL_START write and latch length
        self.comb += start.eq(self._control.re & self._control.storage[SPI_CONTROL_START])
        self.sync += If(self._control.re, length.eq(self._control.storage[SPI_CONTROL_LENGTH:]))

        # XFER done
        self.comb += self._status.status[SPI_STATUS_DONE].eq(done)

        # Clock generation -------------------------------------------------------------------------
        clk_divide  = math.ceil(sys_clk_freq/spi_clk_freq)
        clk_divider = Signal(max=clk_divide)
        clk_rise    = Signal()
        clk_fall    = Signal()
        self.sync += [
            If(clk_rise,   pads.clk.eq(cs)),
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
            done.eq(1),
            If(start,
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
            If(bits == length,
                NextState("END")
            ).Elif(clk_fall,
                NextValue(bits, bits + 1)
            ),
            cs.eq(1),
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
                self.comb += pads.cs_n[i].eq(~self._cs.storage[i] | ~cs)

        # Master Out Slave In (MOSI) generation (generated on spi_clk falling edge) ---------------
        mosi_data = Signal(data_width)
        self.sync += \
            If(start,
                mosi_data.eq(self._mosi.storage)
            ).Elif(clk_rise & shift,
                mosi_data.eq(Cat(Signal(), mosi_data[:-1]))
            ).Elif(clk_fall,
                pads.mosi.eq(mosi_data[-1])
            )

        # Master In Slave Out (MISO) capture (captured on spi_clk rising edge) --------------------
        miso      = Signal()
        miso_data = self._miso.status
        self.sync += \
            If(shift,
                If(clk_rise,
                    miso.eq(pads.miso),
                ).Elif(clk_fall,
                    miso_data.eq(Cat(miso, miso_data[:-1]))
                )
            )
