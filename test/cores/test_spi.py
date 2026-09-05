#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.spi import SPIMaster, SPISlave


class TestSPI(unittest.TestCase):
    def test_spi_master_invalid_parameters(self):
        for data_width in [0, -1, 256, 1.5, True]:
            with self.subTest(data_width=data_width):
                with self.assertRaisesRegex(ValueError, "data_width"):
                    SPIMaster(None, data_width, 100e6, 5e6)
        for sys_freq, spi_freq in [(0, 1), (1, 0), (-1, 1), (float("nan"), 1),
                                   (1, float("inf")), (1, 1), (100e6, 1)]:
            with self.subTest(sys_freq=sys_freq, spi_freq=spi_freq):
                with self.assertRaisesRegex(ValueError, "clock"):
                    SPIMaster(None, 32, sys_freq, spi_freq)

    def test_spi_master_rejects_invalid_requests_and_recovers(self):
        dut = SPIMaster(None, 32, 100e6, 5e6, with_csr=False, mode="aligned")

        def gen():
            yield dut.loopback.eq(1)
            for length, divider in [(0, 2), (33, 2), (255, 2), (8, 0), (8, 1)]:
                yield dut.length.eq(length)
                yield dut.clk_divider.eq(divider)
                yield dut.start.eq(1)
                yield
                self.assertEqual((yield dut.irq), 1)
                yield dut.start.eq(0)
                for _ in range(8):
                    yield
                    self.assertEqual((yield dut.done), 1)
                    self.assertEqual((yield dut.error), 1)
                    self.assertEqual((yield dut.pads.clk), 0)
                    self.assertEqual((yield dut.pads.cs_n), 1)

                yield dut.length.eq(8)
                yield dut.clk_divider.eq(2)
                yield dut.mosi.eq(0xa5)
                yield dut.start.eq(1)
                yield
                yield dut.start.eq(0)
                for _ in range(64):
                    yield
                self.assertEqual((yield dut.done), 1)
                self.assertEqual((yield dut.error), 0)
                self.assertEqual((yield dut.miso) & 0xff, 0xa5)

        run_simulation(dut, gen())

    def test_spi_master_csr_error_status(self):
        dut = SPIMaster(None, 32, 100e6, 5e6)
        def gen():
            yield from dut._control.write(1)  # start, length=0
            yield
            self.assertEqual((yield dut._status.fields.done), 1)
            self.assertEqual((yield dut._status.fields.error), 1)
            yield from dut._control.write((8 << 8) | 1)
            for _ in range(256):
                yield
            self.assertEqual((yield dut._status.fields.done), 1)
            self.assertEqual((yield dut._status.fields.error), 0)
        run_simulation(dut, gen())

    def test_spi_master_lengths_and_odd_dividers(self):
        for data_width in [1, 7, 8, 24, 32, 255]:
            for divider in [2, 3, 5]:
                for mode in ["raw", "aligned"]:
                    with self.subTest(width=data_width, divider=divider, mode=mode):
                        dut = SPIMaster(None, data_width, 100e6, 5e6, with_csr=False, mode=mode)
                        value = ((1 << data_width) - 1) // 3 | 1
                        def gen():
                            yield dut.loopback.eq(1)
                            yield dut.length.eq(data_width)
                            yield dut.clk_divider.eq(divider)
                            yield dut.mosi.eq(value)
                            yield dut.start.eq(1)
                            yield
                            yield dut.start.eq(0)
                            rises = 0
                            previous = 0
                            for _ in range((data_width + 4)*divider):
                                yield
                                clk = (yield dut.pads.clk)
                                rises += clk and not previous
                                previous = clk
                            self.assertEqual(rises, data_width)
                            self.assertEqual((yield dut.done), 1)
                            self.assertEqual((yield dut.error), 0)
                            self.assertEqual((yield dut.miso), value)
                        run_simulation(dut, gen())

    def test_spi_master_latches_transfer_settings(self):
        pads = Record([("clk", 1), ("cs_n", 2), ("mosi", 1), ("miso", 1)])
        dut = SPIMaster(pads, 32, 100e6, 5e6, with_csr=False, mode="aligned")
        def gen():
            yield dut.loopback.eq(1)
            yield dut.length.eq(16)
            yield dut.clk_divider.eq(4)
            yield dut.cs.eq(1)
            yield dut.mosi.eq(0xbeef)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            for _ in range(12):
                yield
            # These settings apply only to a subsequent request. Busy starts are ignored.
            yield dut.length.eq(0)
            yield dut.clk_divider.eq(0)
            yield dut.loopback.eq(0)
            yield dut.cs.eq(2)
            yield dut.mosi.eq(0)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            for _ in range(100):
                if (yield pads.clk):
                    self.assertEqual((yield pads.cs_n), 0b10)
                yield
            self.assertEqual((yield dut.done), 1)
            self.assertEqual((yield dut.error), 0)
            self.assertEqual((yield dut.miso) & 0xffff, 0xbeef)
        run_simulation(dut, gen())

    def test_spi_master_syntax(self):
        spi_master = SPIMaster(pads=None, data_width=32, sys_clk_freq=100e6, spi_clk_freq=5e6)
        self.assertEqual(hasattr(spi_master, "pads"), 1)

    def test_spi_master_xfer_loopback_32b_32b(self):
        def generator(dut):
            yield dut.loopback.eq(1)
            yield dut.clk_divider.eq(2)
            yield dut.mosi.eq(0xdeadbeef)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            yield
            while (yield dut.done) == 0:
                yield
            yield
            self.assertEqual(hex((yield dut.miso)), hex(0xdeadbeef))

        dut = SPIMaster(pads=None, data_width=32, sys_clk_freq=100e6, spi_clk_freq=5e6, with_csr=False)
        run_simulation(dut, generator(dut))

    def test_spi_master_xfer_loopback_32b_16b(self):
        def generator(dut):
            yield dut.loopback.eq(1)
            yield dut.mosi.eq(0xbeef)
            yield dut.length.eq(16)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            yield
            while (yield dut.done) == 0:
                yield
            yield
            self.assertEqual(hex((yield dut.miso)), hex(0xbeef))

        dut = SPIMaster(pads=None, data_width=32, sys_clk_freq=100e6, spi_clk_freq=5e6, with_csr=False, mode="aligned")
        run_simulation(dut, generator(dut))

    def test_spi_master_manual_cs(self):
        pads = Record([("clk", 1), ("cs_n", 1), ("mosi", 1), ("miso", 1)])

        def generator(dut):
            yield dut.clk_divider.eq(2)
            yield dut.cs_mode.eq(1)
            yield dut.cs.eq(1)
            for _ in range(4):
                yield

            # Manual CS mode only controls chip-select lifetime.
            self.assertEqual((yield pads.cs_n), 0)
            for _ in range(8):
                self.assertEqual((yield pads.cs_n), 0)
                self.assertEqual((yield pads.clk), 0)
                yield

            # Transfers still require start/length.
            yield dut.mosi.eq(0xa5)
            yield dut.length.eq(8)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            yield
            while (yield dut.done) == 0:
                self.assertEqual((yield pads.cs_n), 0)
                yield
            yield

            # CS remains asserted after the transfer until software releases it.
            self.assertEqual((yield pads.cs_n), 0)
            yield dut.cs.eq(0)
            for _ in range(4):
                yield
            self.assertEqual((yield pads.cs_n), 1)

        dut = SPIMaster(pads=pads, data_width=32, sys_clk_freq=100e6, spi_clk_freq=5e6, with_csr=False)
        run_simulation(dut, generator(dut))

    def test_spi_slave_syntax(self):
        spi_slave = SPISlave(pads=None, data_width=32)
        self.assertEqual(hasattr(spi_slave, "pads"), 1)

    def test_spi_slave_xfer(self):
        class DUT(Module):
            def __init__(self):
                pads = Record([("clk", 1), ("cs_n", 1), ("mosi", 1), ("miso", 1)])
                self.submodules.master = SPIMaster(pads, data_width=32,
                    sys_clk_freq=100e6, spi_clk_freq=5e6,
                    with_csr=False)
                self.submodules.slave  = SPISlave(pads, data_width=32)

        def master_generator(dut):
            for i in range(8):
                yield
            yield dut.master.mosi.eq(0xdeadbeef)
            yield dut.master.length.eq(32)
            yield dut.master.start.eq(1)
            yield
            yield dut.master.start.eq(0)
            yield
            while (yield dut.master.done) == 0:
                yield
            yield
            self.assertEqual(hex((yield dut.master.miso)), hex(0x12345678))

        def slave_generator(dut):
            for i in range(8):
                yield
            yield dut.slave.miso.eq(0x12345678)
            while (yield dut.slave.start) == 0:
                yield
            while (yield dut.slave.done) == 0:
                yield
            yield
            self.assertEqual(hex((yield dut.slave.mosi)), hex(0xdeadbeef))
            self.assertEqual((yield dut.slave.length), 32)

        dut = DUT()
        run_simulation(dut, [master_generator(dut), slave_generator(dut)])
