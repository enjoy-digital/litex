#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest
from unittest import mock

from migen import ClockDomain, Instance

from litex.gen import LiteXModule
from litex.build.generic_platform import IOStandard, Pins
from litex.build.gowin import gowin
from litex.build.gowin.platform import GowinPlatform
from litex.soc.cores.clock.gowin_gw1n import GW1NPLL


class _ApiculaPlatform(GowinPlatform):
    def __init__(self):
        GowinPlatform.__init__(self,
            device     = "GW1NR-LV9QN88PC6/I5",
            io         = [("clk27", 0, Pins("52"))],
            toolchain  = "apicula",
            devicename = "GW1NR-9C",
        )

    def do_finalize(self, fragment):
        self.add_period_constraint(self.lookup_request("clk27"), 1e9/27e6)


class _ApiculaSoC(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.sys_clk_freq = sys_clk_freq
        self.cd_sys       = ClockDomain()

        clk27 = platform.request("clk27")
        self.pll = pll = GW1NPLL(devicename=platform.devicename, device=platform.device)
        pll.register_clkin(clk27, 27e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)


class TestGowinToolchain(unittest.TestCase):
    def test_cst_pairs_sstl_differential_pins_with_class_suffix(self):
        for standard in ("SSTL15D", "SSTL15D_I", "SSTL18D_II", "LVCMOS15"):
            with self.subTest(standard=standard), tempfile.TemporaryDirectory() as build_dir:
                constraints = [
                    ("dqs_p", ["Y3", "V9"], [IOStandard(standard)], ("ddram", 0, "dqs_p")),
                    ("dqs_n", ["AA3", "V8"], [IOStandard(standard)], ("ddram", 0, "dqs_n")),
                ]
                name = os.path.join(build_dir, "top")
                gowin._build_cst(constraints, [], [], name)
                with open(name + ".cst") as f:
                    cst = f.read()
                if standard == "LVCMOS15":
                    self.assertIn('IO_LOC "dqs_p[0]" Y3;', cst)
                    self.assertIn('IO_LOC "dqs_n[0]" AA3;', cst)
                else:
                    self.assertIn('IO_LOC "dqs_p[0]" Y3,AA3;', cst)
                    self.assertIn('IO_LOC "dqs_p[1]" V9,V8;', cst)
                    self.assertNotIn('IO_LOC "dqs_n', cst)

    def test_generated_clock_chain(self):
        platform = GowinPlatform("GW5AT-LV60PG484AC1/I0",
            io=[("clk50", 0, Pins("A1"))], devicename="GW5AT-60B")
        dut = LiteXModule()
        dut.cd_sys = ClockDomain("sys")
        dut.cd_fast = ClockDomain("fast")
        clk50 = platform.request("clk50")
        dut.specials += Instance("PLLA", i_CLKIN=clk50, o_CLKOUT0=dut.cd_fast.clk)
        dut.specials += Instance("CLKDIV", p_DIV_MODE="4",
            i_HCLKIN=dut.cd_fast.clk, i_RESETN=1, i_CALIB=0, o_CLKOUT=dut.cd_sys.clk)
        platform.add_period_constraint(clk50, 20)
        platform.add_generated_clock_constraint(dut.cd_fast.clk, clk50,
            multiply_by=20, divide_by=3, name="ddr_clk")
        platform.add_generated_clock_constraint(dut.cd_sys.clk, dut.cd_fast.clk, divide_by=4)

        with tempfile.TemporaryDirectory() as build_dir:
            platform.build(dut, build_dir=build_dir, build_name="top", run=False)
            with open(os.path.join(build_dir, "top.sdc")) as f:
                sdc = f.read().splitlines()

        self.assertEqual(sdc, [
            "create_clock -name clk50 -period 20.0 [get_ports {clk50}]",
            "create_generated_clock -name ddr_clk -source [get_ports {clk50}] "
            "-divide_by 3 -multiply_by 20 [get_nets {fast_clk}]",
            "create_generated_clock -name sys_clk -source [get_nets {fast_clk}] "
            "-divide_by 4 -multiply_by 1 [get_nets {sys_clk}]",
        ])

    def test_apicula_uses_generated_system_clock_target(self):
        platform = _ApiculaPlatform()
        soc      = _ApiculaSoC(platform, sys_clk_freq=48e6)

        with tempfile.TemporaryDirectory() as build_dir:
            platform.build(soc, build_dir=build_dir, build_name="top", run=False)
            with open(os.path.join(build_dir, "build_top.sh")) as f:
                build_script = f.read()

        self.assertIn("--freq 48.0", build_script)
        self.assertNotIn("--freq 27.0", build_script)

    def test_wsl_prefers_native_gowin(self):
        def which(tool):
            return {
                "gw_sh"     : "/opt/gowin/IDE/bin/gw_sh",
                "gw_sh.exe" : "/mnt/c/Gowin/IDE/bin/gw_sh.exe",
            }.get(tool)

        with mock.patch.object(gowin, "_is_wsl", return_value=True), \
             mock.patch.object(gowin, "which", side_effect=which):
            gw_sh, gw_sh_path = gowin._find_gowin_shell()

            self.assertEqual(gw_sh, "gw_sh")
            self.assertEqual(gw_sh_path, "/opt/gowin/IDE/bin/gw_sh")
            self.assertFalse(gowin._gowin_uses_windows_paths())

    def test_wsl_falls_back_to_windows_gowin(self):
        def which(tool):
            return {
                "gw_sh"     : None,
                "gw_sh.exe" : "/mnt/c/Gowin/IDE/bin/gw_sh.exe",
            }.get(tool)

        with mock.patch.object(gowin, "_is_wsl", return_value=True), \
             mock.patch.object(gowin, "which", side_effect=which):
            gw_sh, gw_sh_path = gowin._find_gowin_shell()

            self.assertEqual(gw_sh, "gw_sh.exe")
            self.assertEqual(gw_sh_path, "/mnt/c/Gowin/IDE/bin/gw_sh.exe")
            self.assertTrue(gowin._gowin_uses_windows_paths())

    def test_wsl_windows_paths_use_wslpath_and_escape_backslashes(self):
        with mock.patch.object(gowin.subprocess, "check_output", return_value="C:\\proj\\top.v\n"):
            path = gowin._gowin_tcl_path("/mnt/c/proj/top.v", use_windows_paths=True)

        self.assertEqual(path, "C:\\\\proj\\\\top.v")

    def test_wsl_windows_paths_keep_relative_paths(self):
        with mock.patch.object(gowin.subprocess, "check_output") as check_output:
            path = gowin._gowin_tcl_path("top.v", use_windows_paths=True)

        self.assertEqual(path, "top.v")
        check_output.assert_not_called()

    def test_native_wsl_paths_are_not_rewritten(self):
        path = gowin._gowin_tcl_path("/mnt/c/proj/top.v", use_windows_paths=False)

        self.assertEqual(path, "/mnt/c/proj/top.v")


if __name__ == "__main__":
    unittest.main()
