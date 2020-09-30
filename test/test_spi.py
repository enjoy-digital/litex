#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.spi import SPIMaster, SPISlave


class TestSPI(unittest.TestCase):
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
