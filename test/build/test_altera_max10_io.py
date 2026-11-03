#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.build.generic_platform import Pins
from litex.build.altera.platform import AlteraPlatform
from litex.build.io import SDRInput, SDROutput, DDROutput

_io = [
    ("clk", 0, Pins("A1")),
    ("o",   0, Pins("A2")),
    ("i",   0, Pins("A3")),
    ("ck",  0, Pins("A4")),
]

class _DUT(Module):
    def __init__(self, platform, ddr_inputs=(1, 0)):
        self.clock_domains.cd_sys = ClockDomain()
        self.comb += self.cd_sys.clk.eq(platform.request("clk"))
        x = Signal()
        y = Signal()
        self.specials += SDROutput(i=x, o=platform.request("o"))
        self.specials += SDRInput(i=platform.request("i"), o=y)
        self.sync += x.eq(y)
        self.specials += DDROutput(*ddr_inputs, platform.request("ck"), ClockSignal("sys"))

def verilog(device, **kwargs):
    platform = AlteraPlatform(device, _io)
    return str(platform.get_verilog(_DUT(platform, **kwargs)))

class TestAlteraMax10IO(unittest.TestCase):
    def test_max10_sdr_output_and_forwarded_clock(self):
        # MAX 10: SDR outputs are fabric registers, the forwarded clock drives the pin directly,
        # SDR inputs keep ALTDDIO_IN.
        v = verilog("10M50DAF484C7G")
        self.assertNotIn("ALTDDIO_OUT", v)
        self.assertIn("ALTDDIO_IN", v)
        self.assertIn("assign ck = sys_clk;", v)

    def test_max10_inverted_forwarded_clock(self):
        v = verilog("10M50DAF484C7G", ddr_inputs=(0, 1))
        self.assertNotIn("ALTDDIO_OUT", v)
        self.assertIn("assign ck = (~sys_clk);", v)

    def test_max10_ddr_data_output_keeps_altddio(self):
        self.assertIn("ALTDDIO_OUT", verilog("10M50DAF484C7G", ddr_inputs=(Signal(), Signal())))

    def test_other_families_keep_altddio(self):
        self.assertIn("ALTDDIO_OUT", verilog("EP4CE22F17C6"))
        self.assertIn("ALTDDIO_IN",  verilog("EP4CE22F17C6"))
