#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from unittest.mock import patch

from migen import Record
from migen.fhdl.specials import Tristate

from litex.build.generic_platform import Subsignal, Pins, IOStandard
from litex.build.xilinx import XilinxPlatform
from litex.soc.cores.cpu.vexriscv_smp import VexRiscvSMP
from litex.soc.integration.soc import SoCCore, SoCError

_swd_io = [
    ("swd", 0,
        Subsignal("swclk", Pins("A1")),
        Subsignal("swdio", Pins("A2")),
        IOStandard("LVCMOS33"),
    ),
]


class TestCPUSWDDebug(unittest.TestCase):
    def setUp(self):
        for name, value in [("privileged_debug", True), ("jtag_tap", False), ("with_swd", True), ("reset_vector", 0)]:
            context = patch.object(VexRiscvSMP, name, value)
            context.start()
            self.addCleanup(context.stop)

    def make_soc(self, **kwargs):
        platform = XilinxPlatform("xc7a35ticsg324-1L", _swd_io, toolchain="vivado")
        options = dict(
            cpu_type            = "vexriscv_smp",
            integrated_rom_size = 0x8000,
            with_uart           = False,
            with_timer          = False,
            with_ctrl           = False,
        )
        options.update(kwargs)
        return SoCCore(platform, clk_freq=100e6, **options)

    def test_bidirectional_pads(self):
        soc = self.make_soc()
        soc.add_cpu_swd_debug(clk_freq=4e6)
        tristates = [s for s in soc.cpu._fragment.specials if isinstance(s, Tristate)]
        self.assertEqual(len(tristates), 1)
        self.assertIs(tristates[0].oe, soc.cpu.swdio_oe)
        swclk = soc.platform.lookup_request("swd").swclk
        self.assertEqual(soc.platform.toolchain.clocks[swclk][0], 250)
        self.assertEqual(soc.constants["CONFIG_CPU_SWD_DEBUG_CLK_FREQ"], 4000000)

    def test_three_wire_pads(self):
        soc   = self.make_soc()
        pads  = Record([("swclk", 1), ("swdio_i", 1), ("swdio_o", 1), ("swdio_oe", 1)])
        soc.cpu.add_swd(pads)
        self.assertFalse(any(isinstance(s, Tristate) for s in soc.cpu._fragment.specials))

    def test_cpu_without_swd_is_rejected(self):
        VexRiscvSMP.with_swd = False
        soc = self.make_soc()
        with self.assertLogs("SoC", level="ERROR"), self.assertRaises(SoCError):
            soc.add_cpu_swd_debug()

    def test_invalid_clk_freq_is_rejected(self):
        for clk_freq in [0, -1, float("inf"), float("nan")]:
            with self.subTest(clk_freq=clk_freq):
                soc = self.make_soc()
                with self.assertRaises(ValueError):
                    soc.add_cpu_swd_debug(clk_freq=clk_freq)


if __name__ == "__main__":
    unittest.main()
