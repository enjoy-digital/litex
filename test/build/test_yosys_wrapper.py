#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import unittest

from litex.build.yosys_wrapper import YosysWrapper, yosys_args, yosys_argdict


class _Platform:
    def __init__(self):
        self.verilog_include_paths = ["/include"]
        self.sources = [
            ("/src/top.v",      "verilog",       "work"),
            ("/src/pkg.sv",     "systemverilog", "work"),
            ("/src/include.v",  "systemverilog", "work"),
        ]


class TestYosysWrapper(unittest.TestCase):
    def test_systemverilog_defaults_to_read_verilog_sv(self):
        wrapper = YosysWrapper(_Platform(), "top", target="gowin")

        read_files = wrapper._import_sources()

        self.assertIn('read_verilog -sv -I/include "/src/pkg.sv"', read_files)
        self.assertNotIn("read_slang", read_files)

    def test_slang_frontend_groups_systemverilog_sources(self):
        platform = _Platform()
        platform.yosys_use_slang  = True
        platform.yosys_slang_opts = "--ignore-initial --top top"

        wrapper = YosysWrapper(platform, "top", target="gowin")
        read_files = wrapper._import_sources()

        self.assertNotIn("plugin -i slang", read_files)
        self.assertIn('read_verilog -I/include "/src/top.v"', read_files)
        self.assertIn("read_slang --ignore-initial --top top -I/include /src/pkg.sv /src/include.v", read_files)
        self.assertNotIn("read_verilog -sv", read_files)

    def test_slang_frontend_can_load_legacy_plugin(self):
        wrapper = YosysWrapper(_Platform(), "top", target="gowin", slang_plugin=True)

        read_files = wrapper._import_sources()

        self.assertIn("plugin -i slang", read_files)
        self.assertIn("read_slang -I/include /src/pkg.sv /src/include.v", read_files)

    def test_yosys_slang_argdict(self):
        parser = argparse.ArgumentParser()
        yosys_args(parser)

        args = parser.parse_args(["--yosys-slang"])

        self.assertTrue(yosys_argdict(args)["use_slang"])
        self.assertFalse(yosys_argdict(args)["slang_plugin"])

    def test_yosys_slang_plugin_argdict(self):
        parser = argparse.ArgumentParser()
        yosys_args(parser)

        args = parser.parse_args(["--yosys-slang-plugin"])
        argdict = yosys_argdict(args)

        self.assertTrue(argdict["use_slang"])
        self.assertTrue(argdict["slang_plugin"])


if __name__ == "__main__":
    unittest.main()
