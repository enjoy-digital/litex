#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.cores.ov5640 import OV5640Camera


class _Pads:
    def __init__(self):
        self.scl  = Signal()
        self.sda  = Signal()
        self.xclk = Signal()
        self.pwdn = Signal()
        self.rst_n = Signal()


class _DUT(LiteXModule):
    def __init__(self):
        self.camera = OV5640Camera(_Pads(), sys_clk_freq=50e6)


class TestOV5640Camera(unittest.TestCase):
    def test_control_signals_present(self):
        dut = _DUT()
        dut.get_fragment()
        self.assertTrue(hasattr(dut.camera, "i2c"))
        self.assertTrue(hasattr(dut.camera, "control"))


if __name__ == "__main__":
    unittest.main()
