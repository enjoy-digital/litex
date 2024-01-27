#
# This file is part of LiteX.
#
# Copyright (c) 2022 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect.stream import SyncFIFO

class FIFOSyncMacro(LiteXModule, Record):
    """FIFOSyncMacro

    Provides an equivalent of Xilinx' FIFO_SYNC_MACRO which is a unimacro dedicated for 7 series
    FPGAs and Zynq-7000 SoC.

    Detailed informations can be found in official documentation:
    https://docs.xilinx.com/r/2021.2-English/ug953-vivado-7series-libraries/FIFO_SYNC_MACRO
    """
    def __init__(self, fifo_size="18Kb", data_width=32, almost_empty_offset=0, almost_full_offset=0, do_reg=0, toolchain="vivado"):
        assert data_width <= 72
        assert fifo_size in ["18Kb", "36Kb"]
        if do_reg and toolchain != "vivado":
            raise NotImplementedError("FIFOSyncMacro: DO_REG==1 is supported only for Vivado toolchain")

        fifo_sync_macro_layout = [
            ("rd_d",        data_width),
            ("almostfull",  1),
            ("almostempty", 1),
            ("full",        1),
            ("empty",       1),
            ("rdcount",     13),
            ("rderr",       1),
            ("wrerr",       1),
            ("wrcount",     13),
            ("rden",        1),
            ("wr_d",        data_width),
            ("wren",        1),
            ("reset",       1)
        ]
        Record.__init__(self, fifo_sync_macro_layout)

        if toolchain == "vivado":
            self.specials += Instance("FIFO_SYNC_MACRO",
                p_DEVICE              = "7SERIES",
                p_FIFO_SIZE           = fifo_size,
                p_DATA_WIDTH          = data_width,
                p_ALMOST_EMPTY_OFFSET = almost_empty_offset,
                p_ALMOST_FULL_OFFSET  = almost_full_offset,
                p_DO_REG              = do_reg,
                i_CLK         = ClockSignal(),
                i_RST         = self.reset,
                o_ALMOSTFULL  = self.almostfull,
                o_ALMOSTEMPTY = self.almostempty,
                o_FULL        = self.full,
                o_EMPTY       = self.empty,
                i_WREN        = self.wren,
                i_DI          = self.wr_d,
                i_RDEN        = self.rden,
                o_DO          = self.rd_d,
                o_RDCOUNT     = self.rdcount,
                o_RDERR       = self.rderr,
                o_WRCOUNT     = self.wrcount,
                o_WRERR       = self.wrerr,
            )
        else:
            level = Signal(14)

            # FIFO size is adjusted to only match configurations supported by FIFO_SYNC_MACRO
            if fifo_size == "18Kb":
                fifo_size = 16
            elif fifo_size == "36Kb":
                fifo_size = 32
            else:
                raise ValueError("FIFOSyncMacro can only be configured to 18Kb or 36Kb of memory")

            if data_width in range(1, 5):
                macro_data_width = 4
            elif data_width in range(5, 10):
                macro_data_width = 8
            elif data_width in range(10, 19):
                macro_data_width = 16
            elif data_width in range(19, 37):
                macro_data_width = 32
            elif data_width in range(37, 73):
                if fifo_size == 36:
                    macro_data_width = 64
                else:
                    raise ValueError("FIFOSyncMacro accepts data width up to 72 bits only for 36Kb FIFO size.")
            else:
                raise ValueError("FIFOSyncMacro only accepts data width up to 72 bits.")

            self.fifo_depth = fifo_depth = (int)(fifo_size * 1024 / macro_data_width)

            self.fifo = fifo = ResetInserter()(SyncFIFO([("data", data_width)], fifo_depth))

            self.comb += [
                fifo.reset.eq(self.reset),

                level.eq(fifo.level),

                # connect port signals to internal fifo
                # sink
                fifo.sink.data.eq(self.wr_d),
                fifo.sink.valid.eq(self.wren),
                # source
                self.rd_d.eq(fifo.source.data),
                fifo.source.ready.eq(self.rden),

                self.wrerr.eq(~fifo.sink.ready & self.wren),
                self.rderr.eq(fifo.source.ready & self.rden),

                If(level == 0,
                    self.empty.eq(1)
                ).Else(
                    self.empty.eq(0)
                ),

                If(level == fifo_depth,
                    self.full.eq(1)
                ).Else(
                    self.full.eq(0)
                ),
            ]

            self.sync += [
                # reset only these two since other signals are dependent on fifo state
                If(self.reset,
                    self.rdcount.eq(0),
                    self.wrcount.eq(0),
                ),

                # wrcount and rdcount are counters of respectively written and read words
                If(fifo.sink.ready & fifo.sink.valid,
                    If(self.wrcount == (fifo_depth - 1),
                        self.wrcount.eq(0)
                    ).Else(
                        self.wrcount.eq(self.wrcount + 1),
                    )
                ),
                If(fifo.source.ready & fifo.source.valid,
                    If(self.rdcount == (fifo_depth - 1),
                        self.rdcount.eq(0)
                    ).Else(
                        self.rdcount.eq(self.rdcount + 1),
                    )
                ),

                # assert almostempty when fifo level is lower than almost_empty_offset
                If((level <= almost_empty_offset),
                    self.almostempty.eq(1)
                ).Else(
                    self.almostempty.eq(0)
                ),

                # assert almostfull when fifo level is higher than almost_full_offset
                If((level >= (fifo_depth - almost_full_offset)),
                    self.almostfull.eq(1)
                ).Else(
                    self.almostfull.eq(0)
                ),
            ]
