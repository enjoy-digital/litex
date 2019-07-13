# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import unittest

from migen import *

from litex.soc.cores.spi import SPIMaster


class TestSPI(unittest.TestCase):
    def test_spi_master_syntax(self):
        spi_master = SPIMaster(pads=None, data_width=32, sys_clk_freq=100e6, spi_clk_freq=5e6)
        self.assertEqual(hasattr(spi_master, "pads"), 1)

    def test_spi_xfer_loopback(self):
        def generator(dut):
            yield dut.loopback.eq(1)
            yield dut.mosi.eq(0xdeadbeef)
            yield dut.length.eq(32)
            yield dut.start.eq(1)
            yield
            yield dut.start.eq(0)
            yield
            while (yield dut.done) == 0:
                yield
            self.assertEqual((yield dut.miso), 0xdeadbeef)

        dut = SPIMaster(pads=None, data_width=32, sys_clk_freq=100e6, spi_clk_freq=5e6, with_control=False)
        run_simulation(dut, generator(dut))
