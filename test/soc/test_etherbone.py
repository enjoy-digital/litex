#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import LiteXModule

from litex.build.io import CRG
from litex.build.generic_platform import Pins
from litex.build.sim import SimPlatform

from litex.soc.integration.soc_core import SoCMini
from litex.soc.interconnect import stream

try:
    from liteeth.common import eth_phy_description
except ImportError:
    eth_phy_description = None

# Helpers ------------------------------------------------------------------------------------------

class _PHY(LiteXModule):
    """PHY whose clock domains are not named eth_rx/eth_tx (ex Efinix Titanium RGMII: eth0_*)."""
    dw          = 8
    tx_clk_freq = 125e6
    rx_clk_freq = 125e6

    def __init__(self):
        self.sink   = stream.Endpoint(eth_phy_description(8))
        self.source = stream.Endpoint(eth_phy_description(8))
        self.crg    = LiteXModule()
        self.crg.cd_eth_rx = ClockDomain("eth0_rx")
        self.crg.cd_eth_tx = ClockDomain("eth0_tx")


class _SoC(SoCMini):
    def __init__(self, data_width):
        platform = SimPlatform("sim", [("sys_clk", 0, Pins(1)), ("sys_rst", 0, Pins(1))])
        self.crg = CRG(platform.request("sys_clk"))
        SoCMini.__init__(self, platform, 100e6)
        self.ethphy = _PHY()
        self.add_etherbone(phy=self.ethphy, data_width=data_width, with_timing_constraints=False)
        # A UDP user port in the SoC's sys clock domain.
        self.udp_port = self.ethcore_etherbone.udp.crossbar.get_port(0x1234 + 1, dw=32, cd="etherbone")

# Test Etherbone -----------------------------------------------------------------------------------

@unittest.skipIf(eth_phy_description is None, "LiteEth not installed.")
class TestEtherbone(unittest.TestCase):
    def check(self, data_width, core_cd):
        soc = _SoC(data_width)
        self.assertEqual(soc.ethcore_etherbone.cd, core_cd)
        # Elaborates with the PHY's clock domains (an unresolved eth_rx/eth_tx raises).
        soc.platform.get_verilog(soc)

    def test_8bit_core_runs_in_phy_rx_clock_domain(self):
        self.check(8, "eth0_rx")

    def test_32bit_core_uses_phy_clock_domain_names(self):
        self.check(32, "sys")

if __name__ == "__main__":
    unittest.main()
