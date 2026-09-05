#
# This file is part of LiteX.
#
# Copyright (c) 2019-2024 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *

# SPI Master ---------------------------------------------------------------------------------------

class SPIMaster(LiteXModule):
    """4-wire SPI Master

    Implements a 4-wire SPI Master with CPOL=0 and CPHA=0, tailored for FPGA designs. It allows
    configurable data_width and SPI clock frequency at build time. Supports Raw and Aligned modes
    for data transfer and software-controlled Chip Select (CS) for extended SPI operations.

    Parameters:
        pads (Record)             : Interface pads for SPI signals. If None, a default layout is used.
        data_width (int)          : Maximum Data width of SPI transactions.
        sys_clk_freq (int)        : System clock frequency in Hz.
        spi_clk_freq (int)        : Desired SPI clock frequency in Hz.
        with_csr (bool, optional) : Enables CSR interface if True.
        mode (str, optional)      : 'raw' for as-is data transfer or 'aligned' for transaction length-based alignment.

    Modes:
        Raw     : MOSI data is aligned to the core's data-width. Optimal for data-width matching SPI transactions.
        Aligned : MOSI data is aligned based on the transaction's length. Suitable for variable-length SPI transactions.

    CS Control:
        Software-controlled CS is available for scenarios requiring precise control over CS assertion, like
        SPI Flash page programming or when hardware CS lines are insufficient. It allows software to keep
        CS asserted across multiple transfers. Each transfer still has to be started explicitly through the
        ``start``/``length`` control path; manual CS mode does not clock data by itself.

    Transfers require 1..data_width bits and a clock divider of at least 2. Invalid starts leave
    the core idle, set ``error`` and pulse ``irq``. The next valid start clears ``error``. Data,
    length, divider, loopback and automatic CS selection are sampled at start; manual CS remains
    live so software can control its lifetime independently.
    """
    pads_layout = [("clk", 1), ("cs_n", 1), ("mosi", 1), ("miso", 1)]
    def __init__(self, pads, data_width, sys_clk_freq, spi_clk_freq, with_csr=True, mode="raw"):
        if not isinstance(data_width, int) or isinstance(data_width, bool) or not 1 <= data_width <= 255:
            raise ValueError("SPI master data_width must be an integer from 1 to 255.")
        if not all(math.isfinite(f) and f > 0 for f in [sys_clk_freq, spi_clk_freq]):
            raise ValueError("SPI master clock frequencies must be finite and positive.")
        default_divider = math.ceil(sys_clk_freq/spi_clk_freq)
        if not 2 <= default_divider <= 65535:
            raise ValueError("SPI master clock divider must be from 2 to 65535.")
        if mode not in ["raw", "aligned"]:
            raise ValueError("Unsupported SPI master mode: {}.".format(mode))
        self.mode = mode
        if pads is None:
            pads = Record(self.pads_layout)
        if not hasattr(pads, "cs_n"):
            pads.cs_n = Signal()
        if len(pads.cs_n) > 16:
            raise ValueError("SPI master supports up to 16 chip-selects.")
        self.pads       = pads
        self.data_width = data_width

        self.start       = Signal()
        self.length      = Signal(8)
        self.done        = Signal()
        self.error       = Signal()
        self.irq         = Signal()
        self.mosi        = Signal(data_width)
        self.miso        = Signal(data_width)
        self.cs          = Signal(len(pads.cs_n), reset=1)
        self.cs_mode     = Signal()
        self.loopback    = Signal()
        self.clk_divider = Signal(16, reset=default_divider)

        if with_csr:
            self.add_csr()

        # # #

        clk_enable  = Signal()
        xfer_enable = Signal()
        count       = Signal(max=max(data_width, 2))
        mosi_latch  = Signal()
        miso_latch  = Signal()
        length      = Signal(8)
        divider     = Signal(16, reset=default_divider)
        loopback    = Signal()
        cs_latched  = Signal.like(self.cs)
        self.sync += If(mosi_latch,
            length.eq(self.length),
            divider.eq(self.clk_divider),
            loopback.eq(self.loopback),
            cs_latched.eq(self.cs),
        )

        # Clock generation -------------------------------------------------------------------------
        clk_divider = Signal(16)
        clk_rise    = Signal()
        clk_fall    = Signal()
        self.comb += clk_rise.eq(clk_divider == (divider[1:] - 1))
        self.comb += clk_fall.eq(clk_divider == (divider     - 1))
        self.sync += [
            clk_divider.eq(clk_divider + 1),
            If(clk_rise,
                pads.clk.eq(clk_enable),
            ).Elif(clk_fall,
                clk_divider.eq(0),
                pads.clk.eq(0),
            ),
            # Start the newly sampled divider from a known phase.
            If(mosi_latch,
                clk_divider.eq(0),
                pads.clk.eq(0),
            ),
        ]

        # Control FSM ------------------------------------------------------------------------------
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            self.done.eq(1),
            If(self.start,
                If((self.length == 0) | (self.length > data_width) | (self.clk_divider < 2),
                    NextValue(self.error, 1),
                    self.irq.eq(1),
                ).Else(
                    NextValue(self.error, 0),
                    self.done.eq(0),
                    mosi_latch.eq(1),
                    NextState("START"),
                ),
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
                If(count == (length - 1),
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
                cs = Mux(self.cs_mode, self.cs[i], cs_latched[i] & xfer_enable)
                # CS Output/Invert.
                self.sync += pads.cs_n[i].eq(~cs)

        # Master Out Slave In (MOSI) generation (generated on spi_clk falling edge) ----------------
        mosi_data  = Signal(data_width)
        mosi_array = Array(mosi_data[i] for i in range(data_width))
        mosi_sel   = Signal(max=max(data_width, 2))
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
        miso_data = Signal(data_width)
        self.sync += [
            If(clk_rise,
                If(loopback,
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
            CSRField("start",  size=1, offset=0, pulse=True,
                description="SPI Xfer Start (Write ``1`` to start one Xfer)."),
            CSRField("length", size=8, offset=8,
                description=f"SPI Xfer Length (1..{self.data_width} bits). Required for each Xfer, including in manual CS mode.")
        ])
        self._status = CSRStatus(description="SPI Status.", fields=[
            CSRField("done", size=1, offset=0, description="SPI Xfer Done (when read as ``1``)."),
            CSRField("mode", size=1, offset=1, description="SPI mode", values=[
                ("``0b0``", "Raw    : MOSI transfers aligned on core's data-width."),
                ("``0b1``", "Aligned: MOSI transfers aligned on transfers' length."),
            ]),
            CSRField("error", size=1, offset=2,
                description="Invalid length or divider rejected. Cleared by the next valid start."),
        ])
        self.comb += [
            self.start.eq(self._control.fields.start),
            self.length.eq(self._control.fields.length),
            self._status.fields.done.eq(self.done),
            self._status.fields.error.eq(self.error),
            self._status.fields.mode.eq({"raw": 0b0, "aligned": 0b1}[self.mode]),
        ]

        # MOSI/MISO.
        self._mosi = CSRStorage(self.data_width, reset_less=True,
            description="SPI MOSI data (MSB-first serialization). Data is shifted when a Xfer is started.")
        self._miso = CSRStatus(self.data_width,
            description="SPI MISO data (MSB-first de-serialization).")
        self.comb += [
            self.mosi.eq(self._mosi.storage),
            self._miso.status.eq(self.miso),
        ]

        # Chip Select.
        if with_cs:
            self._cs = CSRStorage(description="SPI CS Chip-Select and Mode.", fields=[
                CSRField("sel",  size=len(self.cs), offset=0,  reset=1,
                    description="SPI chip-select value.", values=[
                        ("``0b0..001``", "Chip ``0`` selected for SPI Xfer."),
                        ("``0b1..000``", "Chip ``N`` selected for SPI Xfer.")
                    ]),
                CSRField("mode", size=1, offset=16, reset=0,
                    description="SPI chip-select mode.", values=[
                        ("``0b0``", "Normal operation (CS handled by Core)."),
                        ("``0b1``", "Manual CS operation: CS follows ``sel`` continuously; Xfers still "
                            "require ``start``/``length``. Useful to keep CS asserted across multiple Xfers.")
                    ]),
            ])
            self.comb += [
                self.cs.eq(self._cs.fields.sel),
                self.cs_mode.eq(self._cs.fields.mode)
            ]

        # Loopback.
        if with_loopback:
            self._loopback = CSRStorage(description="SPI Loopback Mode.", fields=[
                CSRField("mode", size=1, description="SPI loopback mode.", values=[
                    ("``0b0``", "Normal operation."),
                    ("``0b1``", "Loopback operation (MOSI to MISO).")
                ])
            ])
            self.comb += self.loopback.eq(self._loopback.fields.mode)

    def add_clk_divider(self):
        self._clk_divider = CSRStorage(16, description="SPI Clk Divider (2..65535), sampled at transfer start.", reset=self.clk_divider.reset)
        self.comb += self.clk_divider.eq(self._clk_divider.storage)
