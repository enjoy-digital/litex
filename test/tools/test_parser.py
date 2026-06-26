#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import contextlib
import io
import unittest

from litex.build.parser import LiteXArgumentParser
from litex.build.xilinx.platform import Xilinx7SeriesPlatform


class _FakePlatform:
    device_family = "unit"

    @staticmethod
    def toolchains(device):
        return ["unit"]

    @staticmethod
    def fill_args(toolchain, parser):
        pass

    @staticmethod
    def get_argdict(toolchain, args):
        return {}


class TestLiteXArgumentParserCPUArguments(unittest.TestCase):
    def make_parser(self):
        return LiteXArgumentParser(
            platform    = _FakePlatform,
            description = "LiteX argument parser test.",
        )

    def help_for(self, *args):
        stdout = io.StringIO()
        parser = self.make_parser()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args([*args, "--help"])

        self.assertEqual(cm.exception.code, 0)
        return stdout.getvalue()

    def test_cpu_none_help_hides_cpu_only_arguments(self):
        help_text = self.help_for("--cpu-type=None")

        self.assertIn("--cpu-type CPU_TYPE", help_text)
        self.assertNotIn("--cpu-variant", help_text)
        self.assertNotIn("--cpu-reset-address", help_text)
        self.assertNotIn("--cpu-cfu", help_text)
        self.assertNotIn("--cpu-count", help_text)
        self.assertNotIn("--integrated-rom-size", help_text)
        self.assertNotIn("--integrated-rom-init", help_text)

    def test_vexriscv_help_keeps_vexriscv_common_cpu_arguments(self):
        help_text = self.help_for("--cpu-type=vexriscv")

        self.assertIn("--cpu-variant", help_text)
        self.assertIn("--cpu-reset-address", help_text)
        self.assertIn("--integrated-rom-size", help_text)
        self.assertIn("--integrated-rom-init", help_text)
        self.assertNotIn("--cpu-cfu", help_text)
        self.assertNotIn("--cpu-count", help_text)

    def test_vexriscv_cfu_variant_help_adds_cpu_cfu_argument(self):
        help_text = self.help_for("--cpu-type=vexriscv", "--cpu-variant=full+cfu")

        self.assertIn("--cpu-cfu", help_text)

    def test_vexriscv_smp_help_adds_smp_specific_arguments(self):
        help_text = self.help_for("--cpu-type=vexriscv_smp")

        self.assertIn("--cpu-variant", help_text)
        self.assertIn("--cpu-reset-address", help_text)
        self.assertIn("--cpu-count", help_text)
        self.assertIn("--with-fpu", help_text)
        self.assertNotIn("--cpu-cfu", help_text)

    def test_cpu_none_rejects_cpu_cfu_argument(self):
        stderr = io.StringIO()
        parser = self.make_parser()

        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args(["--cpu-type=None", "--cpu-cfu", "cfu.v"])

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("unrecognized arguments: --cpu-cfu cfu.v", stderr.getvalue())

    def test_vexriscv_standard_rejects_cpu_cfu_argument(self):
        stderr = io.StringIO()
        parser = self.make_parser()

        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args(["--cpu-type=vexriscv", "--cpu-cfu", "cfu.v"])

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("unrecognized arguments: --cpu-cfu cfu.v", stderr.getvalue())

    def test_cpu_none_rejects_integrated_rom_init_argument(self):
        stderr = io.StringIO()
        parser = self.make_parser()

        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args(["--cpu-type=None", "--integrated-rom-init", "rom.bin"])

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("unrecognized arguments: --integrated-rom-init rom.bin", stderr.getvalue())

    def test_vexriscv_keeps_cpu_cfu_argument(self):
        parser = self.make_parser()

        args = parser.parse_args([
            "--cpu-type=vexriscv",
            "--cpu-variant=full+cfu",
            "--cpu-cfu", "cfu.v",
            "--no-build-log",
        ])

        self.assertEqual(args.cpu_type, "vexriscv")
        self.assertEqual(args.cpu_variant, "full+cfu")
        self.assertEqual(args.cpu_cfu,  "cfu.v")

    def test_bus_arbiter_is_forwarded_to_soc_argdict(self):
        parser = self.make_parser()

        parser.parse_args([
            "--bus-arbiter=transaction",
            "--no-build-log",
        ])

        self.assertEqual(parser.soc_argdict["bus_arbiter"], "transaction")


class TestLiteXArgumentParserXilinxToolchainArguments(unittest.TestCase):
    def make_parser(self):
        return LiteXArgumentParser(
            platform    = Xilinx7SeriesPlatform,
            description = "LiteX Xilinx argument parser test.",
        )

    def help_for(self, *args):
        stdout = io.StringIO()
        parser = self.make_parser()

        with contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as cm:
                parser.parse_args([*args, "--help"])

        self.assertEqual(cm.exception.code, 0)
        return stdout.getvalue()

    def test_xilinx_yosys_nextpnr_help_adds_nextpnr_arguments(self):
        help_text = self.help_for("--toolchain=yosys+nextpnr")

        self.assertIn("--nextpnr-timingstrict", help_text)
        self.assertIn("--nextpnr-seed",         help_text)

    def test_xilinx_openxc7_argdict_keeps_nextpnr_timingstrict(self):
        parser = self.make_parser()

        parser.parse_args([
            "--toolchain=openxc7",
            "--nextpnr-timingstrict",
            "--no-build-log",
        ])

        self.assertTrue(parser.toolchain_argdict["timingstrict"])


if __name__ == "__main__":
    unittest.main()
