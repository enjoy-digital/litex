#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.fhdl import tracer

from litex.gen import LiteXModule


class TestMigenCompat(unittest.TestCase):
    def test_python314_fast_local_opcodes(self):
        for opcode in ["LOAD_FAST_BORROW", "LOAD_FAST_CHECK"]:
            self.assertIn(opcode, tracer._load_build_opcodes)

    def test_clock_domain_name_inference(self):
        class DUT(LiteXModule):
            def __init__(self):
                self.cd_tx = ClockDomain()
                self.cd_sys = ClockDomain(reset_less=True)
                self.clock_domains.cd_rx = ClockDomain()

        dut = DUT()
        self.assertEqual(dut.cd_tx.name, "tx")
        self.assertEqual(dut.cd_sys.name, "sys")


if __name__ == "__main__":
    unittest.main()
