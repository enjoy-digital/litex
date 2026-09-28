#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import re
import unittest

from migen import *

from litex.gen.fhdl import verilog

from litex.build.gowin.common import gowin_special_overrides, gw5a_special_overrides

from litex.soc.cores.usb2_phy.phy        import USB2PHY
from litex.soc.cores.usb2_phy.gowin_gw5a import GW5AUSB2PHYCRG

# USB 2.0 PHY (GW5A) -------------------------------------------------------------------------------

class _DUT(Module):
    def __init__(self):
        self.pads = Record([(name, 1) for name in ["d_p", "d_n", "se_dp", "se_dn", "fs_dp", "fs_dn", "pullup"]])
        self.clock_domains.cd_usb     = ClockDomain()
        self.clock_domains.cd_usb_960 = ClockDomain(reset_less=True)
        self.submodules.crg = crg = GW5AUSB2PHYCRG()
        self.submodules.phy = USB2PHY(self.pads, serdes_rst=crg.serdes_rst)

class TestUSB2PHYGW5A(unittest.TestCase):
    def test_elaboration(self):
        dut = _DUT()
        v   = str(verilog.convert(dut,
            ios               = {*dut.pads.flatten(), dut.cd_usb.clk, dut.cd_usb.rst, dut.cd_usb_960.clk},
            special_overrides = {**gowin_special_overrides, **gw5a_special_overrides},
        ))
        for primitive, name in [
            ("DHCE",        "usb2_phy_dhce"),
            ("CLKDIV",      "usb2_phy_clkdiv"),
            ("OSER16",      "gw5a_oser16"),
            ("IDES16",      "gw5a_ides16"),
            ("ELVDS_IOBUF", "gw5a_elvds_iobuf"),
        ]:
            with self.subTest(primitive=primitive):
                self.assertIsNotNone(re.search(rf"\n{primitive} (#\(.*?\) )?{name}\s*\(", v, re.S))
        # SerDes clocked by the generated High-Speed clocks.
        self.assertIn(".FCLK  (usb_hs_fast_clk)", v)
        self.assertIn(".PCLK  (usb_hs_clk)",      v)

    def test_generic_needs_lowering(self):
        # Portable PHY: without vendor lowering of the SerDes specials, explicit error.
        dut = _DUT()
        with self.assertRaises(NotImplementedError):
            verilog.convert(dut, ios={*dut.pads.flatten(), dut.cd_usb.clk, dut.cd_usb.rst, dut.cd_usb_960.clk})
