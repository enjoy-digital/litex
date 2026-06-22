#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest
from unittest import mock

from migen import *

from litex.build.xilinx.platform import Xilinx7SeriesPlatform


class _MinimalSoC(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain()


class TestXilinxYosysNextpnrToolchain(unittest.TestCase):
    def test_openxc7_no_compile_gateware_does_not_require_toolchain_env(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.dict(os.environ, {
                "CHIPDB":        "",
                "PRJXRAY_DB_DIR": "",
            }):
                platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=False)

            with open(os.path.join(tmp_dir, "build_top.sh")) as f:
                script = f.read()

        self.assertIn("${CHIPDB:?", script)
        self.assertIn("${PRJXRAY_DB_DIR:-", script)
        self.assertIn("nextpnr-xilinx", script)

    def test_openxc7_compile_gateware_still_requires_chipdb_env(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.dict(os.environ, {"CHIPDB": ""}):
                with self.assertRaisesRegex(OSError, "CHIPDB"):
                    platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=True)


if __name__ == "__main__":
    unittest.main()
