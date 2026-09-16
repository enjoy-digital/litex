#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.cores.spilcd import SPILCD, get_st7789_init_sequence


class _Pads:
    def __init__(self):
        self.clk       = Signal()
        self.mosi      = Signal()
        self.miso      = Signal()
        self.cs_n      = Signal()
        self.dc        = Signal()
        self.rst_n     = Signal()
        self.backlight = Signal()


class _DUT(LiteXModule):
    def __init__(self):
        self.spilcd = SPILCD(_Pads(), sys_clk_freq=50e6)


class TestSPILCD(unittest.TestCase):
    def test_control_signals_present(self):
        dut = _DUT()
        dut.get_fragment()
        self.assertTrue(hasattr(dut.spilcd, "spi"))
        self.assertTrue(hasattr(dut.spilcd, "control"))

    def test_common_init_sequence(self):
        sequence = get_st7789_init_sequence()
        self.assertTrue(sequence)
        self.assertTrue(all(len(entry) == 2 for entry in sequence))


if __name__ == "__main__":
    unittest.main()
