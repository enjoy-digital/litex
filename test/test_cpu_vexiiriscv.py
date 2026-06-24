#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import unittest
from types import SimpleNamespace

from litex.soc.cores.cpu.vexiiriscv.core import VexiiRiscv


_UNSET = object()


class TestVexiiRiscvGCCArch(unittest.TestCase):
    def setUp(self):
        self.xlen    = VexiiRiscv.xlen
        self.isa_map = VexiiRiscv.isa_map

    def tearDown(self):
        VexiiRiscv.xlen    = self.xlen
        VexiiRiscv.isa_map = self.isa_map

    def test_gcc_arch_keeps_bios_isa_conservative(self):
        VexiiRiscv.xlen = 64
        VexiiRiscv.isa_map = {
            "i", "m", "a", "f", "d", "c",
            "b", "e", "g", "h", "v",
            "zba", "zbb", "zbc", "zbs",
            "zicbom", "zicntr", "zicsr", "zifencei", "zihpm", "zmmul",
            "zknd", "zkne",
            "shlcofideleg",
            "smaia", "smcntrpmf", "smcsrind",
            "ssaia", "sscofpmf", "sscsrind", "sstc",
        }

        self.assertEqual(VexiiRiscv.get_gcc_arch(), "rv64i2p0_mafdc")

    def test_gcc_arch_matches_float_abi_extensions(self):
        VexiiRiscv.xlen = 32
        VexiiRiscv.isa_map = {"i", "m", "f", "c"}

        self.assertEqual(VexiiRiscv.get_gcc_arch(), "rv32i2p0_mfc")


class TestVexiiRiscvSocArgs(unittest.TestCase):
    def setUp(self):
        self.soc_keys      = getattr(VexiiRiscv, "soc_keys",      _UNSET)
        self.soc_arg_names = getattr(VexiiRiscv, "soc_arg_names", _UNSET)
        self.soc_args      = getattr(VexiiRiscv, "soc_args",      _UNSET)

    def tearDown(self):
        if self.soc_keys is _UNSET and hasattr(VexiiRiscv, "soc_keys"):
            delattr(VexiiRiscv, "soc_keys")
        elif self.soc_keys is not _UNSET:
            VexiiRiscv.soc_keys = self.soc_keys
        if self.soc_arg_names is _UNSET and hasattr(VexiiRiscv, "soc_arg_names"):
            delattr(VexiiRiscv, "soc_arg_names")
        elif self.soc_arg_names is not _UNSET:
            VexiiRiscv.soc_arg_names = self.soc_arg_names
        if self.soc_args is _UNSET and hasattr(VexiiRiscv, "soc_args"):
            delattr(VexiiRiscv, "soc_args")
        elif self.soc_args is not _UNSET:
            VexiiRiscv.soc_args = self.soc_args

    def test_imsic_interrupts_forwards_vexii_socgen_name(self):
        parser = argparse.ArgumentParser()
        VexiiRiscv.args_fill(parser)
        args = parser.parse_args(["--imsic-interrupts=64"])
        VexiiRiscv.soc_args = SimpleNamespace(**{
            key: getattr(args, key) for key in VexiiRiscv.soc_keys
        })

        soc_args = VexiiRiscv._get_soc_args()

        self.assertIn("--imsic-interrupt-number=64", soc_args)
        self.assertNotIn("--imsic-interrupts=64", soc_args)


if __name__ == "__main__":
    unittest.main()
