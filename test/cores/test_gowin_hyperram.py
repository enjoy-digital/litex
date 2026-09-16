#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen import *

from litex.soc.cores.ram.gowin_hyperram import GowinHyperRAM


class _Pads:
    def __init__(self, data_width=16, nchips=1):
        self.clk    = Signal(nchips)
        self.clk_n  = Signal(nchips)
        self.cs_n   = Signal(nchips)
        self.rst_n  = Signal(nchips)
        self.dq     = Signal(data_width*nchips)
        self.rwds   = Signal((data_width//8)*nchips)


class _DUT(LiteXModule):
    def __init__(self):
        self.cd_sys4x = ClockDomain()
        self.hyperram = GowinHyperRAM(_Pads(), sys_clk_freq=27e6, clk_ratio="4:1")


class TestGowinHyperRAM(unittest.TestCase):
    def test_wrapper_creates_tristates(self):
        dut = _DUT()
        fragment = dut.get_fragment()
        tristates = [special for special in fragment.specials if isinstance(special, Tristate)]
        self.assertEqual(len(tristates), 2)


if __name__ == "__main__":
    unittest.main()
