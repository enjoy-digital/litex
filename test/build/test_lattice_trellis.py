#
# This file is part of LiteX.
#
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import tempfile
import unittest

from migen import ClockDomain, Module

from litex.build.lattice.platform import LatticeECP5Platform
from litex.build.parser import LiteXArgumentParser


class TestLatticeTrellisCompression(unittest.TestCase):
    def packer_command(self, **kwargs):
        platform = LatticeECP5Platform("LFE5U-25F-6BG256C", [], toolchain="trellis")
        design = Module()
        design.clock_domains.cd_sys = ClockDomain("sys")

        with tempfile.TemporaryDirectory() as build_dir:
            platform.build(design, build_dir=build_dir, build_name="top", run=False, **kwargs)
            extension = ".bat" if sys.platform in ("win32", "cygwin") else ".sh"
            with open(os.path.join(build_dir, "build_top" + extension)) as f:
                return next(line.split() for line in f if line.startswith("ecppack "))

    def parse_options(self, args, **defaults):
        parser = LiteXArgumentParser(platform=LatticeECP5Platform)
        parser.set_defaults(**defaults)
        parser.parse_args([*args, "--cpu-type=None", "--no-build-log"])
        return parser.toolchain_argdict

    def test_cli_compresses_by_default(self):
        self.assertIn("--compress", self.packer_command(**self.parse_options([])))

    def test_cli_compression_flags(self):
        for flag, compress in [("--ecppack-compress", True), ("--no-ecppack-compress", False)]:
            with self.subTest(flag=flag):
                command = self.packer_command(**self.parse_options([flag]))
                self.assertEqual("--compress" in command, compress)

    def test_cli_compression_default_can_be_overridden(self):
        options = self.parse_options([], ecppack_compress=False)
        self.assertNotIn("--compress", self.packer_command(**options))

    def test_api_can_disable_compression(self):
        self.assertNotIn("--compress", self.packer_command(compress=False))


if __name__ == "__main__":
    unittest.main()
