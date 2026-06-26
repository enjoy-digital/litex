#
# This file is part of LiteX.
#
# Copyright (c) 2022 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from random import Random

from migen import *

from litex.soc.cores.clock import *
from litex.soc.cores.ram.xilinx_fifo_sync_macro import FIFOSyncMacro

class TestFIFOSyncMacro(unittest.TestCase):
    def run_f4pga_queue_stress(self, fifo_size, data_width, cycles=160):
        rnd = Random(42 + data_width)
        dut = FIFOSyncMacro(
            fifo_size,
            data_width          = data_width,
            almost_empty_offset = 3,
            almost_full_offset  = 4,
            toolchain           = "f4pga",
        )
        mask  = 2**data_width - 1
        queue = []

        def generator():
            yield
            for cycle in range(cycles):
                write = rnd.choice([0, 1])
                read  = rnd.choice([0, 1]) and len(queue) > 0
                data  = (cycle*17 + data_width) & mask
                expected_read = queue[0] if read else None

                yield dut.wren.eq(write)
                yield dut.rden.eq(read)
                yield dut.wr_d.eq(data)
                yield

                self.assertEqual((yield dut.wrerr), 0)
                self.assertEqual((yield dut.rderr), 0)

                if read:
                    self.assertEqual((yield dut.rd_d), expected_read)
                    queue.pop(0)
                if write:
                    queue.append(data)

            yield dut.wren.eq(0)
            yield dut.rden.eq(0)
            yield

        run_simulation(dut, generator())

    def test_f4pga_queue_stress(self):
        test_cases = [
            ("18Kb",  1),
            ("18Kb",  9),
            ("18Kb", 32),
            ("36Kb", 64),
        ]
        for fifo_size, data_width in test_cases:
            with self.subTest(fifo_size=fifo_size, data_width=data_width):
                self.run_f4pga_queue_stress(fifo_size, data_width)

    def test_f4pga_reset_clears_state(self):
        def generator(dut):
            for i in range(8):
                yield dut.wren.eq(1)
                yield dut.wr_d.eq(i)
                yield
            yield dut.wren.eq(0)
            yield
            self.assertEqual((yield dut.empty), 0)

            yield dut.reset.eq(1)
            yield
            yield dut.reset.eq(0)
            yield

            self.assertEqual((yield dut.wrcount), 0)
            self.assertEqual((yield dut.rdcount), 0)
            self.assertEqual((yield dut.empty), 1)
            self.assertEqual((yield dut.full), 0)

        dut = FIFOSyncMacro("18Kb", data_width=32, toolchain="f4pga")
        run_simulation(dut, generator(dut))

    def test_f4pga_almost_thresholds(self):
        def write_word(dut, value):
            yield dut.wren.eq(1)
            yield dut.wr_d.eq(value)
            yield
            while (yield dut.fifo.sink.ready) == 0:
                yield
            yield dut.wren.eq(0)
            yield

        def read_word(dut):
            yield dut.rden.eq(1)
            yield
            while (yield dut.fifo.source.valid) == 0:
                yield
            yield dut.rden.eq(0)
            yield

        def generator(dut):
            yield
            self.assertEqual((yield dut.almostempty), 1)
            self.assertEqual((yield dut.almostfull), 0)

            for i in range(dut.fifo_depth - 3):
                yield from write_word(dut, i)
            yield
            self.assertEqual((yield dut.almostfull), 1)

            for _ in range(dut.fifo_depth - 7):
                yield from read_word(dut)
            yield
            self.assertEqual((yield dut.almostempty), 0)

            yield from read_word(dut)
            yield
            self.assertEqual((yield dut.almostempty), 1)

        dut = FIFOSyncMacro(
            "18Kb",
            data_width          = 32,
            almost_empty_offset = 3,
            almost_full_offset  = 3,
            toolchain           = "f4pga",
        )
        run_simulation(dut, generator(dut))

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
                self.assertEqual((yield dut.rderr), 0)
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
                self.assertEqual((yield dut.rderr), 0)
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
