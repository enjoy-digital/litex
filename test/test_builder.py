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

    def get_build_name(self):
        return self.platform.name


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


class _IncludeFakeSoC:
    def __init__(self):
        self.mem_regions = {
            "rom"  : SoCRegion(origin=0x00000000, size=0x1000, mode="rx"),
            "sram" : SoCRegion(origin=0x10000000, size=0x1000),
            "csr"  : SoCRegion(origin=0xe0000000, size=0x10000, cached=False),
        }
        self.constants   = {"CONFIG_CLOCK_FREQUENCY": 100000000}
        self.csr_regions = {}
        self.csr         = SimpleNamespace(ordering="big")
        self.cpu         = SimpleNamespace(
            reset_address        = 0x00000000,
            linker_output_format = "elf32-littleriscv",
        )


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


class TestBuilderPaths(unittest.TestCase):
    def test_default_directories_and_exports_are_under_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = _make_builder(tmp_dir)

            self.assertEqual(builder.output_dir,    os.path.abspath(tmp_dir))
            self.assertEqual(builder.gateware_dir,  os.path.join(os.path.abspath(tmp_dir), "gateware"))
            self.assertEqual(builder.software_dir,  os.path.join(os.path.abspath(tmp_dir), "software"))
            self.assertEqual(builder.include_dir,   os.path.join(os.path.abspath(tmp_dir), "software", "include"))
            self.assertEqual(builder.generated_dir, os.path.join(os.path.abspath(tmp_dir), "software", "include", "generated"))
            self.assertEqual(builder.csr_csv,       os.path.join(os.path.abspath(tmp_dir), "csr.csv"))
            self.assertEqual(builder.csr_json,      os.path.join(os.path.abspath(tmp_dir), "csr.json"))

    def test_output_filename_helpers(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = _make_builder(tmp_dir)

            self.assertEqual(
                builder.get_bios_filename(),
                os.path.join(builder.software_dir, "bios", "bios.bin"),
            )
            self.assertEqual(
                builder.get_bitstream_filename(),
                os.path.join(builder.gateware_dir, "unit.bit"),
            )
            self.assertEqual(
                builder.get_bitstream_filename(mode="flash"),
                os.path.join(builder.gateware_dir, "unit.bin"),
            )
            self.assertEqual(
                builder.get_bitstream_filename(ext=".fs"),
                os.path.join(builder.gateware_dir, "unit.fs"),
            )
            with self.assertRaisesRegex(ValueError, "Unsupported bitstream mode"):
                builder.get_bitstream_filename(mode="invalid")


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

    def test_json_constant_exclusion_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_file = os.path.join(tmp_dir, "remote.json")
            with open(json_file, "w") as f:
                json.dump({
                    "csr_bases": {},
                    "constants": {
                        "timer0_interrupt": 1,
                    },
                    "memories": {},
                }, f)

            builder = _make_builder(tmp_dir)
            builder.add_json(json_file, exclude_constants=[])

            self.assertEqual(builder._get_json_constants()["TIMER0_INTERRUPT"], 1)


class TestBuilderGeneratedFiles(unittest.TestCase):
    def test_generate_includes_without_bios_writes_runtime_headers_only(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            memory_x = os.path.join(tmp_dir, "memory.x")
            builder  = _make_builder(tmp_dir, soc=_IncludeFakeSoC(), memory_x=memory_x)

            with patch("litex.soc.cores.bitbang.collect_i2c_info", return_value=([], [])):
                builder._generate_includes(with_bios=False)

            generated_dir = builder.generated_dir
            self.assertTrue(os.path.exists(os.path.join(generated_dir, "mem.h")))
            self.assertTrue(os.path.exists(os.path.join(generated_dir, "soc.h")))
            self.assertTrue(os.path.exists(os.path.join(generated_dir, "csr.h")))
            self.assertTrue(os.path.exists(os.path.join(generated_dir, "git.h")))
            self.assertTrue(os.path.exists(memory_x))
            self.assertFalse(os.path.exists(os.path.join(generated_dir, "variables.mak")))
            self.assertFalse(os.path.exists(os.path.join(generated_dir, "output_format.ld")))
            self.assertFalse(os.path.exists(os.path.join(generated_dir, "regions.ld")))

    def test_generate_includes_with_bios_writes_linker_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = _make_builder(tmp_dir, soc=_IncludeFakeSoC(), compile_software=False)

            with patch("litex.soc.integration.builder.export.get_cpu_mak", return_value=[
                ("TRIPLE",        "--not-found--"),
                ("CPU",           "unitcpu"),
                ("CPUFAMILY",     "riscv"),
                ("CPUFLAGS",      ""),
                ("CPUENDIANNESS", "little"),
                ("CLANG",         "0"),
                ("CPU_DIRECTORY", tmp_dir),
            ]):
                with patch("litex.soc.cores.bitbang.collect_i2c_info", return_value=([], [])):
                    builder._generate_includes(with_bios=True)

            generated_dir = builder.generated_dir
            self.assertTrue(os.path.exists(os.path.join(generated_dir, "variables.mak")))
            self.assertTrue(os.path.exists(os.path.join(generated_dir, "output_format.ld")))
            self.assertTrue(os.path.exists(os.path.join(generated_dir, "regions.ld")))

    def test_generate_csr_map_writes_default_csv_and_json_exports(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = _make_builder(tmp_dir, soc=_IncludeFakeSoC())

            builder._generate_csr_map()

            with open(builder.csr_json) as f:
                csr_json = json.load(f)
            with open(builder.csr_csv) as f:
                csr_csv = f.read()

            self.assertEqual(csr_json["constants"]["config_clock_frequency"], 100000000)
            self.assertIn("memory_region,csr,0xe0000000,65536", csr_csv)

    def test_variables_contents_escapes_makefile_paths_and_validates_console(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = _make_builder(tmp_dir, soc=_IncludeFakeSoC(), compile_software=False)
            builder.add_software_package("custom", r"C:\liteX\custom")

            with patch("litex.soc.integration.builder.export.get_cpu_mak", return_value=[
                ("TRIPLE",        "--not-found--"),
                ("CPU",           "unitcpu"),
                ("CPUFAMILY",     "riscv"),
                ("CPUFLAGS",      ""),
                ("CPUENDIANNESS", "little"),
                ("CLANG",         "0"),
                ("CPU_DIRECTORY", r"C:\cpu"),
            ]):
                variables = builder._get_variables_contents()
                builder.bios_console = "invalid"
                with self.assertRaisesRegex(ValueError, "Unsupported BIOS console"):
                    builder._get_variables_contents()

            self.assertIn(r"CUSTOM_DIRECTORY=C:\\liteX\\custom", variables)
            self.assertIn("BIOS_CONSOLE_FULL=1", variables)


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

    def test_generate_rom_software_skips_bios_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = object.__new__(Builder)
            builder.software_dir       = tmp_dir
            builder.compile_software   = True
            builder.software_packages  = [
                ("libbase", os.path.join(tmp_dir, "libbase_src")),
                ("bios",    os.path.join(tmp_dir, "bios_src")),
            ]

            with patch("litex.soc.integration.builder.os.cpu_count", return_value=2):
                with patch("litex.soc.integration.builder.subprocess.check_call") as check_call:
                    builder._generate_rom_software(compile_bios=False)

            check_call.assert_called_once_with([
                "make", "-j2",
                "-C", os.path.join(tmp_dir, "libbase"),
                "-f", os.path.join(tmp_dir, "libbase_src", "Makefile"),
            ])

    def test_generate_rom_software_is_noop_when_software_compile_is_disabled(self):
        builder = object.__new__(Builder)
        builder.software_dir       = "software"
        builder.compile_software   = False
        builder.software_packages  = [("libbase", "libbase_src")]

        with patch("litex.soc.integration.builder.subprocess.check_call") as check_call:
            builder._generate_rom_software()

        check_call.assert_not_called()

    def test_prepare_rom_software_creates_all_package_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            builder = object.__new__(Builder)
            builder.software_dir      = tmp_dir
            builder.software_packages = [
                ("libbase", "libbase_src"),
                ("bios",    "bios_src"),
            ]

            builder._prepare_rom_software()

            self.assertTrue(os.path.isdir(os.path.join(tmp_dir, "libbase")))
            self.assertTrue(os.path.isdir(os.path.join(tmp_dir, "bios")))

    def test_check_meson_accepts_supported_version(self):
        builder = object.__new__(Builder)

        with patch("litex.soc.integration.builder.shutil.which", return_value="/usr/bin/meson"):
            with patch("litex.soc.integration.builder.subprocess.check_output", return_value=b"0.60.0\n"):
                builder._check_meson()

    def test_check_meson_rejects_missing_or_old_version(self):
        builder = object.__new__(Builder)

        with patch("litex.soc.integration.builder.shutil.which", return_value=None):
            with self.assertRaisesRegex(OSError, "Unable to find valid Meson"):
                builder._check_meson()

        with patch("litex.soc.integration.builder.shutil.which", return_value="/usr/bin/meson"):
            with patch("litex.soc.integration.builder.subprocess.check_output", return_value=b"0.58.0\n"):
                with self.assertRaisesRegex(OSError, "Meson version too old"):
                    builder._check_meson()


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

    def test_build_copies_marked_platform_sources_to_gateware_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_dir = os.path.join(tmp_dir, "src")
            os.makedirs(source_dir)
            copied_source = os.path.join(source_dir, "copied.v")
            kept_source   = os.path.join(source_dir, "kept.v")
            with open(copied_source, "w") as f:
                f.write("module copied(); endmodule\n")
            with open(kept_source, "w") as f:
                f.write("module kept(); endmodule\n")

            soc = _BuildableFakeSoC()
            soc.platform.sources = [
                (copied_source, "verilog", "work", True),
                (kept_source,   "verilog", "work"),
            ]
            builder = _make_builder(tmp_dir, soc=soc, compile_software=False, compile_gateware=False)

            builder._generate_includes = Mock()
            builder._generate_csr_map  = Mock()
            builder.build()

            self.assertTrue(os.path.exists(os.path.join(builder.gateware_dir, "copied.v")))
            self.assertEqual(soc.platform.sources, [
                ("copied.v",  "verilog", "work"),
                (kept_source, "verilog", "work"),
            ])

    def test_build_preserves_explicit_run_and_hierarchical_kwargs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            soc     = _BuildableFakeSoC()
            builder = _make_builder(
                tmp_dir,
                soc=soc,
                compile_software=False,
                compile_gateware=False,
                build_backend="edalize",
                hierarchical=True,
            )

            builder._generate_includes = Mock()
            builder._generate_csr_map  = Mock()
            builder.build(run=True, hierarchical=False, build_name="top")

            _, kwargs = soc.build_calls[0]
            self.assertTrue(kwargs["run"])
            self.assertFalse(kwargs["hierarchical"])
            self.assertEqual(kwargs["build_backend"], "edalize")
            self.assertEqual(kwargs["build_name"], "top")

    def test_build_removes_software_dir_when_variables_change(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            soc     = _BuildableFakeSoC()
            builder = _make_builder(tmp_dir, soc=soc, compile_gateware=False)
            stale_file = os.path.join(builder.software_dir, "stale.txt")

            os.makedirs(builder.generated_dir)
            with open(os.path.join(builder.generated_dir, "variables.mak"), "w") as f:
                f.write("old")
            with open(stale_file, "w") as f:
                f.write("stale")

            builder._get_variables_contents = Mock(return_value="new")
            builder._generate_includes      = Mock()
            builder._generate_csr_map       = Mock()

            builder.build()

            self.assertFalse(os.path.exists(stale_file))
            self.assertTrue(os.path.isdir(builder.software_dir))

    def test_build_keeps_software_dir_when_variables_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            soc     = _BuildableFakeSoC()
            builder = _make_builder(tmp_dir, soc=soc, compile_gateware=False)
            stale_file = os.path.join(builder.software_dir, "stale.txt")

            os.makedirs(builder.generated_dir)
            with open(os.path.join(builder.generated_dir, "variables.mak"), "w") as f:
                f.write("same")
            with open(stale_file, "w") as f:
                f.write("stale")

            builder._get_variables_contents = Mock(return_value="same")
            builder._generate_includes      = Mock()
            builder._generate_csr_map       = Mock()

            builder.build()

            self.assertTrue(os.path.exists(stale_file))


if __name__ == "__main__":
    unittest.main()
