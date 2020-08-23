#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.bitbang import I2CMaster, SPIMaster

class TestBitBang(unittest.TestCase):
    def test_i2c_master_syntax(self):
        i2c_master = I2CMaster()
        self.assertEqual(hasattr(i2c_master, "pads"), 1)
        i2c_master = I2CMaster(Record(I2CMaster.pads_layout))
        self.assertEqual(hasattr(i2c_master, "pads"), 1)

    def test_spi_master_syntax(self):
        spi_master = SPIMaster()
        self.assertEqual(hasattr(spi_master, "pads"), 1)
        spi_master = SPIMaster(Record(SPIMaster.pads_layout))
        self.assertEqual(hasattr(spi_master, "pads"), 1)
