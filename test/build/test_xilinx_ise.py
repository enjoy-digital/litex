#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest

from migen import *

from litex.build.generic_platform import IOStandard, Pins
from litex.build.xilinx import XilinxSpartan6Platform
from litex.build.xilinx.ise import XilinxISEToolchain


_io = [
    ("clk50",    0, Pins("P2"), IOStandard("LVCMOS33")),
    ("user_led", 0, Pins("P1"), IOStandard("LVCMOS33")),
]


class _Spartan6Platform(XilinxSpartan6Platform):
    default_clk_name   = "clk50"
    default_clk_period = 20.0

    def __init__(self, device="xc6slx9-2-tqg144"):
        XilinxSpartan6Platform.__init__(self, device, _io, toolchain="ise")


class _MinimalSoC(Module):
    def __init__(self, led):
        counter = Signal(8)
        self.sync += counter.eq(counter + 1)
        self.comb += led.eq(counter[-1])


class TestXilinxISEToolchain(unittest.TestCase):
    def test_synplify_spartan6_device_split(self):
        split_device = XilinxISEToolchain._split_synplify_spartan6_device

        self.assertEqual(split_device("xc6slx45-csg324-3"),   ("xc6slx45",  "csg324", "-3"))
        self.assertEqual(split_device("xc6slx9-2-tqg144"),    ("xc6slx9",   "tqg144", "-2"))
        self.assertEqual(split_device("xc6slx9-tqg144-2"),    ("xc6slx9",   "tqg144", "-2"))
        self.assertEqual(split_device("xc6slx45t-fgg484-3"),  ("xc6slx45t", "fgg484", "-3"))
        self.assertEqual(split_device("xc6slx100-2-fgg484"),  ("xc6slx100", "fgg484", "-2"))

    def test_synplify_mode_generates_project_and_script(self):
        platform = _Spartan6Platform()
        platform.toolchain.synplify_cmd = "synplify_pro"
        platform.toolchain.synplify_opt = "set_option -resource_sharing 1"

        with tempfile.TemporaryDirectory() as tmp_dir:
            platform.build(
                _MinimalSoC(platform.request("user_led")),
                build_dir  = tmp_dir,
                build_name = "top",
                run        = False,
                mode       = "synplify",
            )

            with open(os.path.join(tmp_dir, "top_synplify.prj")) as f:
                prj = f.read()
            with open(os.path.join(tmp_dir, "build_top.sh")) as f:
                script = f.read()

        self.assertIn("set_option -technology spartan6", prj)
        self.assertIn("set_option -part xc6slx9", prj)
        self.assertIn("set_option -package tqg144", prj)
        self.assertIn("set_option -speed_grade -2", prj)
        self.assertIn("set_option -resource_sharing 1", prj)
        self.assertIn("add_file -verilog", prj)
        self.assertIn("synplify_pro -batch -runall top_synplify.prj", script)
        self.assertIn("edif2ngd top.edif top.ngo", script)
        self.assertLess(
            script.index("synplify_pro"),
            script.index("edif2ngd top.edif top.ngo"),
        )


if __name__ == "__main__":
    unittest.main()
