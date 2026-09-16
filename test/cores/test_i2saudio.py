#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.sim import run_simulation

from litex.gen import *

from litex.soc.cores.i2saudio import I2SAudio


class _Pads:
    def __init__(self):
        self.bclk = Signal()
        self.lrck = Signal()
        self.dout = Signal()


class _DUT(LiteXModule):
    def __init__(self):
        self.i2s = I2SAudio(_Pads(), sys_clk_freq=100e6, sample_rate=48000, data_width=16, bits_per_channel=16)


class TestI2SAudio(unittest.TestCase):
    def test_clock_generation(self):
        dut = _DUT()

        def generator():
            for _ in range(2000):
                yield
            # After enough cycles BCLK and LRCLK must have toggled.
            self.assertNotEqual((yield dut.i2s.pads.lrck), 0)

        run_simulation(dut, generator(), clocks={"sys": 10})


if __name__ == "__main__":
    unittest.main()
