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
        self.mode = mode
        if pads is None:
            pads = Record(self.pads_layout)
        if not hasattr(pads, "cs_n"):
            pads.cs_n = Signal()
        assert len(pads.cs_n) <= 16
        self.pads       = pads
        self.data_width = data_width

        self.start       = Signal()
        self.length      = Signal(8)
        self.done        = Signal()
        self.irq         = Signal()
        self.mosi        = Signal(data_width)
        self.miso        = Signal(data_width)
        self.cs          = Signal(len(pads.cs_n), reset=1)
        self.cs_mode     = Signal()
        self.loopback    = Signal()
        self.clk_divider = Signal(16, reset=math.ceil(sys_clk_freq/spi_clk_freq))

        if with_csr:
            self.add_csr()

        # # #

        clk_enable  = Signal()
        xfer_enable = Signal()
        count       = Signal(max=data_width)
        mosi_latch  = Signal()
        miso_latch  = Signal()

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
                xfer_enable.eq(1),
                NextState("RUN")
            )
        )
        fsm.act("RUN",
            clk_enable.eq(1),
            xfer_enable.eq(1),
            If(clk_fall,
                NextValue(count, count + 1),
                If(count == (self.length - 1),
                    NextState("STOP")
                )
            )
        )
        fsm.act("STOP",
            xfer_enable.eq(1),
            If(clk_rise,
                miso_latch.eq(1),
                self.irq.eq(1),
                NextState("IDLE")
            )
        )

        # Chip Select generation -------------------------------------------------------------------
        if hasattr(pads, "cs_n"):
            for i in range(len(pads.cs_n)):
                # CS set when enabled and (Xfer enabled or Manual CS mode selected).
                cs = (self.cs[i] & (xfer_enable | (self.cs_mode == 1)))
                # CS Output/Invert.
                self.sync += pads.cs_n[i].eq(~cs)

        # Master Out Slave In (MOSI) generation (generated on spi_clk falling edge) ----------------
        mosi_data  = Signal(data_width)
        mosi_array = Array(mosi_data[i] for i in range(data_width))
        mosi_sel   = Signal(max=data_width)
        self.sync += [
            If(mosi_latch,
                mosi_data.eq(self.mosi),
                mosi_sel.eq((self.length-1) if mode == "aligned" else (data_width-1)),
            ).Elif(clk_fall,
                If(xfer_enable, pads.mosi.eq(mosi_array[mosi_sel])),
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
        # Control / Status.
        self._control = CSRStorage(description="SPI Control.", fields=[
            CSRField("start",  size=1, offset=0, pulse=True, description="SPI Xfer Start (Write ``1`` to start Xfer)."),
            CSRField("length", size=8, offset=8,             description="SPI Xfer Length (in bits).")
        ])
        self._status = CSRStatus(description="SPI Status.", fields=[
            CSRField("done", size=1, offset=0, description="SPI Xfer Done (when read as ``1``)."),
            CSRField("mode", size=1, offset=1, description="SPI mode", values=[
                ("``0b0``", "Raw    : MOSI transfers aligned on core's data-width."),
                ("``0b1``", "Aligned: MOSI transfers aligned on transfers' length."),
            ]),
        ])
        self.comb += [
            self.start.eq(self._control.fields.start),
            self.length.eq(self._control.fields.length),
            self._status.fields.done.eq(self.done),
            self._status.fields.mode.eq({"raw": 0b0, "aligned": 0b1}[self.mode]),
        ]

        # MOSI/MISO.
        self._mosi = CSRStorage(self.data_width, reset_less=True, description="SPI MOSI data (MSB-first serialization).")
        self._miso = CSRStatus(self.data_width,                   description="SPI MISO data (MSB-first de-serialization).")
        self.comb += [
            self.mosi.eq(self._mosi.storage),
            self._miso.status.eq(self.miso),
        ]

        # Chip Select.
        if with_cs:
            self._cs = CSRStorage(description="SPI CS Chip-Select and Mode.", fields=[
                CSRField("sel",  size=len(self.cs), offset=0,  reset=1, values=[
                    ("``0b0..001``", "Chip ``0`` selected for SPI Xfer."),
                    ("``0b1..000``", "Chip ``N`` selected for SPI Xfer.")
                ]),
                CSRField("mode", size=1,            offset=16, reset=0, values=[
                    ("``0b0``", "Normal operation (CS handled by Core)."),
                    ("``0b1``", "Manual operation (CS handled by User, direct recopy of ``sel``), useful for Bulk transfers.")
                ]),
            ])
            self.comb += [
                self.cs.eq(self._cs.fields.sel),
                self.cs_mode.eq(self._cs.fields.mode)
            ]

        # Loopback.
        if with_loopback:
            self._loopback = CSRStorage(description="SPI Loopback Mode.", fields=[
                CSRField("mode", size=1, values=[
                    ("``0b0``", "Normal operation."),
                    ("``0b1``", "Loopback operation (MOSI to MISO).")
                ])
            ])
            self.comb += self.loopback.eq(self._loopback.fields.mode)

    def add_clk_divider(self):
        self._clk_divider = CSRStorage(16, description="SPI Clk Divider.", reset=self.clk_divider.reset)
        self.comb += self.clk_divider.eq(self._clk_divider.storage)
