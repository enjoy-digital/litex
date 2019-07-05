# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import unittest

from migen import *

from litex.soc.cores.spi import SPIMaster

class TestSPI(unittest.TestCase):
    def test_spi_master_syntax(self):
        spi_master = SPIMaster(pads=None, data_width=32, sys_clk_freq=100e6, spi_clk_freq=5e6)
        self.assertEqual(hasattr(spi_master, "pads"), 1)
