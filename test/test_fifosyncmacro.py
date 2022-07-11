#
# This file is part of LiteX.
#
# Copyright (c) 2022 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.clock import *
from litex.soc.cores.ram.xilinx_fifo_sync_macro import FIFOSyncMacro

class TestFIFOSyncMacro(unittest.TestCase):
    def testWriteRead(self):
        def generator(dut):
            # Check initial status
            yield
            self.assertEqual((yield dut.almostempty), 1)
            self.assertEqual((yield dut.empty), 1)
            self.assertEqual((yield dut.almostfull), 0)
            self.assertEqual((yield dut.full), 0)

            # Load values into FIFO
            for i in range(100):
                yield dut.wren.eq(1)
                yield dut.wr_d.eq(i)
                yield
                while (yield dut.fifo.sink.ready) == 0:
                    yield
                yield dut.wren.eq(0)
                yield

            # Check if values are queued
            self.assertEqual((yield dut.wrcount), 100)
            self.assertEqual((yield dut.rdcount), 0)
            self.assertEqual((yield dut.almostempty), 1)
            self.assertEqual((yield dut.empty), 0)
            self.assertEqual((yield dut.almostfull), 0)
            self.assertEqual((yield dut.full), 0)

            # Read and check values
            for i in range(100):
                yield dut.rden.eq(1)
                yield
                self.assertEqual((yield dut.rd_d), i)
                yield dut.rden.eq(0)
                yield

            # Check if status is updated
            self.assertEqual((yield dut.wrcount), 100)
            self.assertEqual((yield dut.rdcount), 100)
            self.assertEqual((yield dut.almostempty), 1)
            self.assertEqual((yield dut.empty), 1)
            self.assertEqual((yield dut.almostfull), 0)
            self.assertEqual((yield dut.full), 0)


        dut = FIFOSyncMacro("18Kb", data_width=32, almost_empty_offset=128,
                            almost_full_offset=128, toolchain="f4pga")

        run_simulation(dut, generator(dut))

    def testWrRdErrors(self):
        def generator(dut):
            # Load values into FIFO
            for i in range(500):
                yield dut.wren.eq(1)
                yield dut.wr_d.eq(i)
                yield
                while (yield dut.fifo.sink.ready) == 0:
                    yield
                yield dut.wren.eq(0)
                yield

            # Check if values are queued
            self.assertEqual((yield dut.wrcount), 500)
            self.assertEqual((yield dut.rdcount), 0)
            self.assertEqual((yield dut.almostempty), 0)
            self.assertEqual((yield dut.empty), 0)
            self.assertEqual((yield dut.almostfull), 1)
            self.assertEqual((yield dut.full), 0)
            self.assertEqual((yield dut.wrerr), 0)
            self.assertEqual((yield dut.rderr), 0)

            # Load to queue 511 values since the next one will overflow wrcount
            for i in range(11):
                yield dut.wren.eq(1)
                yield dut.wr_d.eq(500 + i)
                yield
                while (yield dut.fifo.sink.ready) == 0:
                    yield
                self.assertEqual((yield dut.wrcount), 500 + i)
                yield dut.wren.eq(0)
                yield
            self.assertEqual((yield dut.wrcount), 511)

            # Next load should overflow wrcount and make FIFO full
            yield dut.wren.eq(1)
            yield dut.wr_d.eq(511)
            yield
            while (yield dut.fifo.sink.ready) == 0:
                yield
            yield dut.wren.eq(0)
            yield
            self.assertEqual((yield dut.wrcount), 0)
            self.assertEqual((yield dut.almostfull), 1)
            self.assertEqual((yield dut.full), 1)
            self.assertEqual((yield dut.wrerr), 0)

            # Every next load should cause wrerr assert since FIFO is already full
            yield dut.wren.eq(1)
            yield dut.wr_d.eq(512)
            yield

            # Check if status is updated
            self.assertEqual((yield dut.wrcount), 0)
            self.assertEqual((yield dut.rdcount), 0)
            self.assertEqual((yield dut.almostempty), 0)
            self.assertEqual((yield dut.empty), 0)
            self.assertEqual((yield dut.almostfull), 1)
            self.assertEqual((yield dut.full), 1)
            self.assertEqual((yield dut.wrerr), 1)
            self.assertEqual((yield dut.rderr), 0)
            yield dut.wren.eq(0)
            yield

            # Read values until max rdcount
            for i in range(511):
                yield dut.rden.eq(1)
                yield
                while (yield dut.fifo.source.valid) == 0:
                    yield
                self.assertEqual((yield dut.rd_d), i)
                yield dut.rden.eq(0)
                yield
            self.assertEqual((yield dut.rdcount), 511)
            self.assertEqual((yield dut.almostempty), 1)

            # Next read should make FIFO empty
            yield dut.rden.eq(1)
            yield
            yield dut.rden.eq(0)
            yield
            self.assertEqual((yield dut.almostempty), 1)
            self.assertEqual((yield dut.empty), 1)

            # FIFO is empty so every next read should cause rderr assert
            yield dut.rden.eq(1)
            yield

            # Check if status is updated
            self.assertEqual((yield dut.wrcount), 0)
            self.assertEqual((yield dut.rdcount), 0)
            self.assertEqual((yield dut.almostempty), 1)
            self.assertEqual((yield dut.empty), 1)
            self.assertEqual((yield dut.almostfull), 0)
            self.assertEqual((yield dut.full), 0)
            self.assertEqual((yield dut.wrerr), 0)
            self.assertEqual((yield dut.rderr), 1)


        dut = FIFOSyncMacro("18Kb", data_width=32, almost_empty_offset=128,
                            almost_full_offset=128, toolchain="f4pga")

        run_simulation(dut, generator(dut))
