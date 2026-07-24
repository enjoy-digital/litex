#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from litex.build.generic_platform import GenericPlatform
from litex.soc.cores.cpu.ibex import core as ibex_core


def _create_ibex_tree(root):
    rtl = os.path.join(root, "rtl")
    os.makedirs(rtl)
    with open(os.path.join(rtl, "ibex_core.f"), "w", encoding="utf-8") as f:
        f.write("// comment\n")
        f.write("\n")
        f.write("ibex_if_stage.sv\n")


class TestIbexSources(unittest.TestCase):
    def _add_sources(self, platform, root):
        with mock.patch.object(ibex_core, "get_data_mod", return_value=SimpleNamespace(data_location=root)):
            ibex_core.Ibex.add_sources(platform)

    def test_add_sources_requests_yosys_slang(self):
        with tempfile.TemporaryDirectory() as root:
            _create_ibex_tree(root)
            platform = GenericPlatform("unit", [])

            self._add_sources(platform, root)

        sources = [os.path.relpath(source[0], root) for source in platform.sources]
        source_languages = {
            os.path.relpath(source[0], root): source[1]
            for source in platform.sources
        }

        self.assertTrue(platform.yosys_use_slang)
        self.assertIn("--top ibex_top", platform.yosys_slang_opts)
        self.assertIn("-G RegFile=0", platform.yosys_slang_opts)
        self.assertIn("--infer-input-ports-as-vars", platform.yosys_slang_opts)
        self.assertNotIn("--ignore-unknown-modules", platform.yosys_slang_opts)
        self.assertEqual(source_languages[os.path.join("syn", "rtl", "prim_clock_gating.v")], "systemverilog")
        self.assertIn(os.path.join("vendor", "lowrisc_ip", "ip", "prim_generic", "rtl", "prim_generic_flop.sv"), sources)
        self.assertIn(os.path.join("dv", "uvm", "core_ibex", "common", "prim", "prim_flop.sv"), sources)
        self.assertNotIn(os.path.join("rtl", "ibex_register_file_fpga.sv"), sources)

    def test_add_sources_can_select_fpga_regfile_for_yosys_slang(self):
        with tempfile.TemporaryDirectory() as root:
            _create_ibex_tree(root)
            platform = GenericPlatform("unit", [])
            platform.ibex_regfile = "fpga"

            self._add_sources(platform, root)

        sources = [os.path.relpath(source[0], root) for source in platform.sources]
        self.assertIn("-G RegFile=1", platform.yosys_slang_opts)
        self.assertIn(os.path.join("rtl", "ibex_register_file_fpga.sv"), sources)

    def test_add_sources_rejects_unknown_regfile(self):
        with tempfile.TemporaryDirectory() as root:
            _create_ibex_tree(root)
            platform = GenericPlatform("unit", [])
            platform.ibex_regfile = "missing"

            with self.assertRaisesRegex(ValueError, "ibex_regfile"):
                self._add_sources(platform, root)


if __name__ == "__main__":
    unittest.main()
