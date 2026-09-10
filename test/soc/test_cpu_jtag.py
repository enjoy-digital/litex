#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import os
import tempfile
import unittest
from unittest.mock import patch

from migen import ClockDomain, Instance, Module

from litex.build.xilinx import XilinxPlatform
from litex.soc.cores.cpu.vexriscv_smp import VexRiscvSMP
from litex.soc.integration.soc import SoCCore, SoCError, soc_core_args, soc_core_argdict


class TestCPUJTAGDebug(unittest.TestCase):
    def setUp(self):
        for name, value in [("privileged_debug", True), ("jtag_tap", False), ("reset_vector", 0)]:
            context = patch.object(VexRiscvSMP, name, value)
            context.start()
            self.addCleanup(context.stop)

    def make_soc(self, device="xc7a35ticsg324-1L", **kwargs):
        platform = XilinxPlatform(device, [], toolchain="vivado")
        options = dict(
            cpu_type            = "vexriscv_smp",
            integrated_rom_size = 0x8000,
            with_uart           = False,
            with_timer          = False,
            with_ctrl           = False,
        )
        options.update(kwargs)
        return SoCCore(platform, clk_freq=100e6, **options)

    def test_cpu_debug_mode_does_not_implicitly_connect_jtag(self):
        for privileged_debug in [False, True]:
            with self.subTest(privileged_debug=privileged_debug):
                VexRiscvSMP.privileged_debug = privileged_debug
                soc = self.make_soc()
                self.assertFalse(hasattr(soc, "cpu_jtag_debug"))
                self.assertFalse(hasattr(soc.platform, "_xilinx_jtag_chains"))

    def test_user_chain_and_clock_options(self):
        soc = self.make_soc(
            with_cpu_jtag_debug     = True,
            cpu_jtag_debug_chain    = 2,
            cpu_jtag_debug_clk_freq = 5e6,
        )
        self.assertEqual(soc.cpu_jtag_debug.chain, 2)
        self.assertEqual(soc.platform.toolchain.clocks[soc.cpu_jtag_debug.tck][0], 200)
        self.assertEqual(soc.constants["CONFIG_CPU_JTAG_DEBUG_CHAIN"], 2)
        self.assertEqual(soc.constants["CONFIG_CPU_JTAG_DEBUG_CLK_FREQ"], 5000000)

    def test_external_tap_is_rejected_before_allocating_a_chain(self):
        VexRiscvSMP.jtag_tap = True
        soc = self.make_soc()
        with self.assertLogs("SoC", level="ERROR") as logs, self.assertRaises(SoCError):
            soc.add_cpu_jtag_debug()
        self.assertIn("JTAG instruction interface", " ".join(logs.output))
        self.assertFalse(hasattr(soc.platform, "_xilinx_jtag_chains"))

    def test_cpu_without_debug_port_is_rejected(self):
        soc = self.make_soc(cpu_type=None)
        with self.assertLogs("SoC", level="ERROR"), self.assertRaises(SoCError):
            soc.add_cpu_jtag_debug()

    def test_unsupported_device_is_rejected(self):
        for device in ["LFE5U-85F-6BG381C", "xc7z020clg400-1", "xczu7ev-ffvc1156-2-e"]:
            with self.subTest(device=device):
                soc = self.make_soc(device=device)
                with self.assertLogs("SoC", level="ERROR"), self.assertRaises(SoCError):
                    soc.add_cpu_jtag_debug()
                self.assertFalse(hasattr(soc.platform, "_xilinx_jtag_chains"))

    def test_invalid_chain_is_rejected(self):
        for chain in [0, 5, -1, 1.5, "4"]:
            with self.subTest(chain=chain), self.assertRaisesRegex(ValueError, "integer from 1 to 4"):
                self.make_soc(with_cpu_jtag_debug=True, cpu_jtag_debug_chain=chain)

    def test_invalid_clock_is_rejected_before_allocating_a_chain(self):
        for clk_freq in [0, -1, float("inf"), float("nan")]:
            with self.subTest(clk_freq=clk_freq):
                soc = self.make_soc()
                with self.assertRaisesRegex(ValueError, "finite and positive"):
                    soc.add_cpu_jtag_debug(clk_freq=clk_freq)
                soc.add_cpu_jtag_debug()

    def test_duplicate_attachment_is_rejected_even_on_another_chain(self):
        soc = self.make_soc(with_cpu_jtag_debug=True)
        with self.assertLogs("SoC", level="ERROR"), self.assertRaises(SoCError):
            soc.add_cpu_jtag_debug(chain=2)

    def test_jtagbone_and_debug_can_use_different_chains(self):
        soc = self.make_soc(with_jtagbone=True, with_cpu_jtag_debug=True)
        self.assertEqual(soc.jtagbone.phy.jtag.chain, 1)
        self.assertEqual(soc.cpu_jtag_debug.chain, 4)

    def test_chain_collision_is_rejected_in_both_addition_orders(self):
        for debug_first in [False, True]:
            with self.subTest(debug_first=debug_first):
                soc = self.make_soc()
                if debug_first:
                    soc.add_cpu_jtag_debug()
                    with self.assertRaisesRegex(ValueError, "chain 4 is already in use"):
                        soc.add_jtagbone(chain=4)
                else:
                    soc.add_jtagbone(chain=4)
                    with self.assertRaisesRegex(ValueError, "chain 4 is already in use"):
                        soc.add_cpu_jtag_debug()

    def test_jtag_uart_reserves_its_chain(self):
        soc = self.make_soc(with_uart=True, uart_name="jtag_uart")
        with self.assertRaisesRegex(ValueError, "chain 1 is already in use"):
            soc.add_cpu_jtag_debug(chain=1)
        soc.add_cpu_jtag_debug(chain=4)

    def test_chain_allocation_is_local_to_each_platform(self):
        first = self.make_soc(with_cpu_jtag_debug=True)
        second = self.make_soc(with_cpu_jtag_debug=True)
        self.assertEqual(first.cpu_jtag_debug.chain, second.cpu_jtag_debug.chain)

    def test_bscan_ports_and_constraints_without_a_crg_attribute(self):
        # Exercise actual Verilog/XDC generation, while keeping CPU netlist generation out of
        # this transport test. The instruction signals stand in for the CPU instance's ports.
        soc = self.make_soc(with_cpu_jtag_debug=True, cpu_jtag_debug_clk_freq=5e6)
        dut = Module()
        dut.clock_domains.cd_sys = ClockDomain("sys")
        dut.submodules.jtag = soc.cpu_jtag_debug
        dut.comb += soc._fragment.comb
        ports = [getattr(soc.cpu, "jtag_" + name) for name in
                 ["clk", "tdi", "tdo", "enable", "capture", "shift", "update", "reset"]]
        # Preserve the CPU-facing signals as top-level ports for inspection.
        with tempfile.TemporaryDirectory() as tmpdir:
            soc.platform.build(dut, build_dir=tmpdir, build_name="cpu_jtag", run=False,
                               ios=set(ports + [dut.cd_sys.clk]))
            with open(os.path.join(tmpdir, "cpu_jtag.v")) as f:
                verilog = f.read()
            with open(os.path.join(tmpdir, "cpu_jtag.xdc")) as f:
                xdc = f.read()
        for port in ["TCK", "TDI", "TDO", "SEL", "CAPTURE", "SHIFT", "UPDATE", "RESET"]:
            self.assertIn("." + port, verilog)
        self.assertIn("BSCANE2", verilog)
        self.assertRegex(verilog, r"\.JTAG_CHAIN\s*\(3'd4\)")
        self.assertIn("-period 200.0", xdc)
        self.assertIn("get_nets debug_sys_clk", xdc)
        self.assertRegex(xdc, r"set_clock_groups .* -asynchronous")

    def test_spartan6_uses_its_own_primitive(self):
        soc = self.make_soc(device="xc6slx45-csg324-3", with_cpu_jtag_debug=True)
        primitives = [s.of for s in soc.cpu_jtag_debug._fragment.specials if isinstance(s, Instance)]
        self.assertEqual(primitives, ["BSCAN_SPARTAN6"])

    def test_cli_options_reach_soc_constructor(self):
        parser = argparse.ArgumentParser()
        soc_core_args(parser)
        args = parser.parse_args([
            "--with-cpu-jtag-debug",
            "--cpu-jtag-debug-chain=2",
            "--cpu-jtag-debug-clk-freq=5e6",
        ])
        options = soc_core_argdict(args)
        self.assertTrue(options["with_cpu_jtag_debug"])
        self.assertEqual(options["cpu_jtag_debug_chain"], 2)
        self.assertEqual(options["cpu_jtag_debug_clk_freq"], 5e6)
