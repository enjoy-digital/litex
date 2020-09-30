#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.spi_opi import S7SPIOPI


class TestI2S(unittest.TestCase):
    def test_s7spiopi_syntax(self):
        spi_opi_pads = Record([("dqs", 1), ("dq", 8), ("sclk", 1), ("cs_n", 1), ("ecs_n", 1)])
        spi_opi = S7SPIOPI(pads=spi_opi_pads)

