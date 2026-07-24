#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest
from unittest import mock

from migen import ClockDomain

from litex.gen import LiteXModule
from litex.build.generic_platform import Pins
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
