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
    def __init__(self, with_dvp=False):
        self.scl  = Signal()
        self.sda  = Signal()
        self.xclk = Signal()
        self.pwdn = Signal()
        self.rst_n = Signal()
        if with_dvp:
            self.pclk  = Signal()
            self.href  = Signal()
            self.vsync = Signal()
            self.data  = Signal(8)


class _DUT(LiteXModule):
    def __init__(self, with_dvp=False, fifo_depth=0):
        self.camera = OV5640Camera(_Pads(with_dvp), sys_clk_freq=50e6, fifo_depth=fifo_depth)


class TestOV5640Camera(unittest.TestCase):
    def test_control_signals_present(self):
        dut = _DUT()
        dut.get_fragment()
        self.assertTrue(hasattr(dut.camera, "i2c"))
        self.assertTrue(hasattr(dut.camera, "control"))

    def test_dvp_capture_endpoint(self):
        dut = _DUT(with_dvp=True)
        dut.get_fragment()
        self.assertTrue(hasattr(dut.camera, "source"))
        self.assertTrue(hasattr(dut.camera, "frame_start"))
        self.assertTrue(hasattr(dut.camera, "line_end"))

    def test_dvp_capture_fifo(self):
        dut = _DUT(with_dvp=True, fifo_depth=4)
        dut.get_fragment()
        self.assertTrue(hasattr(dut.camera, "capture_fifo"))


if __name__ == "__main__":
    unittest.main()
