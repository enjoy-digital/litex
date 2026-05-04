#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from litex.soc.integration.builder import Builder, builder_argdict, builder_args
from litex.soc.integration.soc import SoCRegion


class _FakePlatform:
    def __init__(self):
        self.name       = "unit"
        self.sources    = []
        self.output_dir = None

    def get_bitstream_extension(self, mode):
        return {
            "sram"  : ".bit",
            "flash" : ".bin",
        }[mode]


class _FakeSoC:
    def __init__(self, cpu_type=None):
        self.platform = _FakePlatform()
        self.cpu_type = cpu_type


class _BuildableFakeSoC(_FakeSoC):
    def __init__(self):
        _FakeSoC.__init__(self, cpu_type="unitcpu")
        self.cpu         = SimpleNamespace(use_rom=False)
        self.finalized   = 0
        self.build_calls = []
        self.exit_calls  = []

    def finalize(self):
        self.finalized += 1

    def build(self, build_dir, **kwargs):
        self.build_calls.append((build_dir, kwargs))
        return "vns"

    def do_exit(self, vns):
        self.exit_calls.append(vns)


class _RomFakeSoC:
    def __init__(self):
        self.bus = SimpleNamespace(
            data_width = 32,
            regions    = {"rom": SoCRegion(origin=0x00000000, size=16, mode="rx")},
        )
        self.cpu            = SimpleNamespace(endianness="little")
        self.init_rom_calls = []

    def init_rom(self, name, contents, auto_size):
        self.init_rom_calls.append((name, contents, auto_size))


def _make_builder(output_dir, soc=None, **kwargs):
    if soc is None:
        soc = _FakeSoC()
    return Builder(soc, output_dir=output_dir, **kwargs)


def _make_argdict(*args):
    parser = argparse.ArgumentParser()
    builder_args(parser)
    return builder_argdict(parser.parse_args(list(args)))


class TestBuilderArguments(unittest.TestCase):
    def test_no_compile_disables_software_and_gateware(self):
        argdict = _make_argdict("--no-compile")

        self.assertFalse(argdict["compile_software"])
        self.assertFalse(argdict["compile_gateware"])

    def test_individual_compile_flags_are_mapped(self):
        no_software = _make_argdict("--no-compile-software")
        no_gateware = _make_argdict("--no-compile-gateware")

        self.assertFalse(no_software["compile_software"])
        self.assertTrue(no_software["compile_gateware"])
        self.assertTrue(no_gateware["compile_software"])
        self.assertFalse(no_gateware["compile_gateware"])

    def test_export_and_bios_options_are_mapped(self):
        argdict = _make_argdict(
            "--soc-json", "soc.json",
            "--soc-csv", "soc.csv",
            "--soc-svd", "soc.svd",
            "--memory-x", "memory.x",
            "--bios-lto",
            "--bios-format", "float",
            "--bios-console", "lite",
            "--libc-mode", "full",
            "--no-integrated-rom-auto-size",
            "--hierarchical-verilog",
        )

        self.assertEqual(argdict["csr_json"], "soc.json")
        self.assertEqual(argdict["csr_csv"],  "soc.csv")
        self.assertEqual(argdict["csr_svd"],  "soc.svd")
        self.assertEqual(argdict["memory_x"], "memory.x")
        self.assertTrue(argdict["bios_lto"])
        self.assertEqual(argdict["bios_format"],  "float")
        self.assertEqual(argdict["bios_console"], "lite")
        self.assertEqual(argdict["libc_mode"],    "full")
        self.assertFalse(argdict["integrated_rom_auto_size"])
        self.assertTrue(argdict["hierarchical"])


class TestBuilderJsonImports(unittest.TestCase):
    def test_json_imports_are_namespaced_and_interrupt_constants_are_filtered(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_file = os.path.join(tmp_dir, "remote.json")
            with open(json_file, "w") as f:
                json.dump({
                    "csr_bases": {
                        "uart": "0xe0001800",
                    },
                    "csr_registers": {
                        "uart_rx": {
                            "addr" : "0xe0001800",
                            "size" : 1,
                        },
                    },
                    "constants": {
                        "config_csr_data_width" : 32,
                        "uart_interrupt"        : 5,
                        "with_feature"          : True,
                    },
                    "memories": {
                        "rom": {
                            "base" : "0x10000000",
                            "size" : "0x1000",
                            "type" : "rx",
                        },
                    },
                }, f)

            builder = _make_builder(tmp_dir)
            builder.add_json(json_file, origin=0x1000, name="remote")

            constants = builder._get_json_constants()
            mems      = builder._get_json_mem_regions()
            csrs      = builder._get_json_csr_regions()

            self.assertEqual(constants["REMOTE_WITH_FEATURE"], True)
            self.assertNotIn("REMOTE_UART_INTERRUPT", constants)
            self.assertEqual(mems["remote_rom"].origin, 0x10001000)
            self.assertEqual(mems["remote_rom"].size,   0x1000)
            self.assertEqual(csrs["remote_uart"].origin, 0xe0002800)

    def test_json_item_collisions_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = _make_builder(tmp_dir)

            with self.assertRaisesRegex(ValueError, "JSON constant collision on FOO"):
                builder._merge_json_items({"FOO": 1}, {"FOO": 2}, "constant")


class TestBuilderRomSoftware(unittest.TestCase):
    def _make_rom_builder(self, tmp_dir, auto_size):
        builder = object.__new__(Builder)
        builder.software_dir              = tmp_dir
        builder.integrated_rom_auto_size  = auto_size
        builder.soc                       = _RomFakeSoC()
        return builder

    def test_initialize_rom_software_keeps_auto_size_contents_unpadded(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = self._make_rom_builder(tmp_dir, auto_size=True)
            bios_file = os.path.join(tmp_dir, "bios", "bios.bin")

            with patch("litex.soc.integration.builder.soc_core.get_mem_data", return_value=[1, 2]) as get_mem_data:
                builder._initialize_rom_software()

            get_mem_data.assert_called_once_with(bios_file, data_width=32, endianness="little")
            self.assertEqual(builder.soc.init_rom_calls, [("rom", [1, 2], True)])

    def test_initialize_rom_software_pads_when_auto_size_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = self._make_rom_builder(tmp_dir, auto_size=False)
            bios_file = os.path.join(tmp_dir, "bios", "bios.bin")

            with patch("litex.soc.integration.builder.soc_core.get_mem_data", return_value=[1, 2]) as get_mem_data:
                builder._initialize_rom_software()

            get_mem_data.assert_called_once_with(bios_file, data_width=32, endianness="little")
            self.assertEqual(builder.soc.init_rom_calls, [("rom", [1, 2, 0, 0], False)])


class TestBuilderBuild(unittest.TestCase):
    def test_build_adds_bios_package_only_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            soc     = _BuildableFakeSoC()
            builder = _make_builder(tmp_dir, soc=soc, compile_software=False, compile_gateware=False)

            builder._generate_includes = Mock()
            builder._generate_csr_map  = Mock()

            builder.build()
            builder.build()

            bios_packages = [package for package in builder.software_packages if package[0] == "bios"]
            self.assertEqual(len(bios_packages), 1)
            self.assertEqual(soc.finalized, 2)
            self.assertEqual(len(soc.build_calls), 2)
            self.assertFalse(soc.build_calls[0][1]["run"])
            self.assertEqual(soc.exit_calls, ["vns", "vns"])

    def test_build_preserves_user_added_bios_package(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            soc     = _BuildableFakeSoC()
            builder = _make_builder(tmp_dir, soc=soc, compile_software=False, compile_gateware=False)
            bios_dir = os.path.join(tmp_dir, "custom_bios")

            builder.add_software_package("bios", bios_dir)
            builder._generate_includes = Mock()
            builder._generate_csr_map  = Mock()

            builder.build()

            bios_packages = [package for package in builder.software_packages if package[0] == "bios"]
            self.assertEqual(bios_packages, [("bios", bios_dir)])


if __name__ == "__main__":
    unittest.main()
