#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import tempfile
import unittest
from unittest import mock

from migen import *

from litex.build.xilinx.platform import Xilinx7SeriesPlatform


_OPENXC7_ENV_VARS = (
    "CHIPDB", "PRJXRAY_DB_DIR", "NEXTPNR_XILINX_DIR",
    "ARTIX7_CHIPDB", "KINTEX7_CHIPDB", "SPARTAN7_CHIPDB", "VIRTEX7_CHIPDB", "ZYNQ7_CHIPDB",
)


class _MinimalSoC(Module):
    def __init__(self):
        self.clock_domains.cd_sys = ClockDomain()


def _clear_openxc7_env():
    return {name: "" for name in _OPENXC7_ENV_VARS}


def _read_script(build_dir):
    with open(os.path.join(build_dir, "build_top.sh")) as f:
        return f.read()


class TestXilinxYosysNextpnrToolchain(unittest.TestCase):
    def test_openxc7_no_compile_gateware_does_not_require_toolchain_env(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with mock.patch.dict(os.environ, _clear_openxc7_env()):
                with mock.patch("litex.build.xilinx.yosys_nextpnr.which", return_value=None):
                    with mock.patch("litex.build.xilinx.yosys_nextpnr._openxc7_prefix",
                            return_value=os.path.join(tmp_dir, "prefix")):
                        platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=False)
            script = _read_script(tmp_dir)

        self.assertIn("${CHIPDB:-" + os.path.join(tmp_dir, "chipdb") + "}/xc7k325tffg900.bin", script)
        self.assertIn(
            "${PRJXRAY_DB_DIR:-" + os.path.join(tmp_dir, "prefix", "share", "nextpnr", "prjxray-db") + "}", script)
        self.assertIn("fasm2frames --part xc7k325tffg900-2", script)
        self.assertIn("xc7frames2bit", script)
        self.assertNotIn("/snap/", script)

    def test_openxc7_family_chipdb_env(self):
        # The nix container exports one <FAMILY>_CHIPDB per family.
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")
        with tempfile.TemporaryDirectory() as tmp_dir:
            chipdb = os.path.join(tmp_dir, "chipdb")
            os.makedirs(chipdb)
            env = _clear_openxc7_env()
            env["KINTEX7_CHIPDB"] = chipdb
            with mock.patch.dict(os.environ, env):
                with mock.patch("litex.build.xilinx.yosys_nextpnr.which", return_value=None):
                    with mock.patch("litex.build.xilinx.yosys_nextpnr._openxc7_prefix",
                            return_value=os.path.join(tmp_dir, "prefix")):
                        platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=False)
            script = _read_script(tmp_dir)
        self.assertIn("${CHIPDB:-" + chipdb + "}/xc7k325tffg900.bin", script)

    def test_openxc7_source_layout_is_discovered_from_prefix(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            prefix  = os.path.realpath(os.path.join(tmp_dir, "openxc7"))
            prjxray = os.path.join(prefix, "share", "nextpnr", "prjxray-db")
            os.makedirs(os.path.join(prjxray, "kintex7"))

            env = _clear_openxc7_env()
            env["NEXTPNR_XILINX_DIR"] = prefix
            with mock.patch.dict(os.environ, env):
                with mock.patch("litex.build.xilinx.yosys_nextpnr.which", return_value=None):
                    platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=False)
            script = _read_script(tmp_dir)

        self.assertIn("${PRJXRAY_DB_DIR:-" + prjxray + "}", script)
        self.assertIn("${CHIPDB:-" + os.path.join(tmp_dir, "chipdb") + "}/xc7k325tffg900.bin", script)

    def test_openxc7_prefers_fpga_as(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            prefix = os.path.join(tmp_dir, "prefix")
            os.makedirs(os.path.join(prefix, "bin"))
            fpga_as = os.path.join(prefix, "bin", "fpga-as")
            with open(fpga_as, "w") as f:
                f.write("#!/bin/sh\nexit 0\n")

            env = _clear_openxc7_env()
            env.update({
                "NEXTPNR_XILINX_DIR": prefix,
                "CHIPDB":             os.path.join(tmp_dir, "chipdb"),
                "PRJXRAY_DB_DIR":     os.path.join(tmp_dir, "prjxray-db"),
            })
            with mock.patch.dict(os.environ, env):
                with mock.patch("litex.build.xilinx.yosys_nextpnr.which", return_value=None):
                    platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=False)
            script = _read_script(tmp_dir)

        self.assertIn(f"{fpga_as} --prjxray_db_path=${{PRJXRAY_DB_DIR:-", script)
        self.assertIn("--part xc7k325tffg900-2 top.fasm > top.bit", script)
        self.assertNotIn("fasm2frames", script)
        self.assertNotIn("xc7frames2bit", script)

    def test_openxc7_generates_missing_chipdb_with_xilinx_gen(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            prefix     = os.path.join(tmp_dir, "prefix")
            prjxray_db = os.path.join(tmp_dir, "prjxray-db")
            chipdb_dir = os.path.join(tmp_dir, "chipdb")
            xilinx_gen_dir = os.path.join(
                prefix, "share", "nextpnr", "himbaechel", "uarch", "xilinx", "gen")
            os.makedirs(xilinx_gen_dir)
            os.makedirs(os.path.join(prefix, "bin"))
            os.makedirs(os.path.join(prjxray_db, "kintex7"))

            xilinx_gen = os.path.join(xilinx_gen_dir, "xilinx_gen.py")
            with open(xilinx_gen, "w") as f:
                f.write("")
            bbasm = os.path.join(prefix, "bin", "bbasm")
            with open(bbasm, "w") as f:
                f.write("")

            commands = []
            def fake_run(command, *args, **kwargs):
                commands.append(command)
                if "--bba" in command:
                    with open(command[command.index("--bba") + 1], "w") as f:
                        f.write("")
                return mock.Mock(returncode=0)

            def fake_which(name):
                if name in ("yosys", "nextpnr-xilinx"):
                    return "/usr/bin/" + name
                return None

            fake_subprocess = mock.Mock()
            fake_subprocess.run = fake_run
            fake_toolchain_subprocess = mock.Mock()
            fake_toolchain_subprocess.call = mock.Mock(return_value=0)

            env = _clear_openxc7_env()
            env.update({
                "NEXTPNR_XILINX_DIR": prefix,
                "CHIPDB":             chipdb_dir,
                "PRJXRAY_DB_DIR":     prjxray_db,
            })
            with mock.patch.dict(os.environ, env):
                with mock.patch("litex.build.xilinx.yosys_nextpnr.which", side_effect=fake_which):
                    with mock.patch("litex.build.xilinx.yosys_nextpnr.subprocess", fake_subprocess):
                        with mock.patch("litex.build.yosys_nextpnr_toolchain.which", side_effect=fake_which):
                            with mock.patch("litex.build.yosys_nextpnr_toolchain.subprocess", fake_toolchain_subprocess):
                                platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=True)

            chipdb = os.path.join(chipdb_dir, "xc7k325tffg900.bin")
            bba    = os.path.join(chipdb_dir, "xc7k325tffg900.bba")
            self.assertEqual(commands[0][0], "python3")
            self.assertEqual(commands[0][1], xilinx_gen)
            self.assertEqual(commands[0][commands[0].index("--xray") + 1],
                os.path.join(prjxray_db, "kintex7"))
            self.assertEqual(commands[0][commands[0].index("--device") + 1], "xc7k325t")
            self.assertEqual(commands[1], [bbasm, "-l", bba, chipdb])
            self.assertFalse(os.path.exists(bba))

    def test_openxc7_compile_gateware_reports_missing_generator(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            env = _clear_openxc7_env()
            env.update({
                "NEXTPNR_XILINX_DIR": os.path.join(tmp_dir, "prefix"),
                "CHIPDB":             os.path.join(tmp_dir, "chipdb"),
                "PRJXRAY_DB_DIR":     os.path.join(tmp_dir, "prjxray-db"),
            })
            with mock.patch.dict(os.environ, env):
                with self.assertRaisesRegex(OSError, "xilinx_gen.py"):
                    platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=True)

    def test_openxc7_part_normalization(self):
        cases = [
            # device                        part                         dbpart                  die            family
            ("xc7k325t-ffg900-2",           "xc7k325tffg900-2",          "xc7k325tffg900",       "xc7k325t",     "kintex7"),
            ("xc7a100t-2fgg484",            "xc7a100tfgg484-2",          "xc7a100tfgg484",       "xc7a100t",     "artix7"),
            ("xc7a35ticsg324-1L",           "xc7a35tcsg324-1",           "xc7a35tcsg324",        "xc7a50t",      "artix7"),
            ("xc7vx485t-ffg1761-2",         "xc7vx485tffg1761-2",        "xc7vx485tffg1761",     "xc7vx485t",    "virtex7"),
            ("xc7z007sclg400-1",            "xc7z007sclg400-1",          "xc7z007sclg400",       "xc7z010",      "zynq7"),
            ("xc7k325t",                    "xc7k325t",                  "xc7k325t",             "xc7k325t",     "kintex7"),
            ("xc7a35tcpg236-2L",            "xc7a35tcpg236-2L",          "xc7a35tcpg236",        "xc7a50t",      "artix7"),
            ("xc7s15ftgb196-1IL",           "xc7s15ftgb196-1IL",         "xc7s15ftgb196",        "xc7s15",       "spartan7"),
        ]

        for device, part, dbpart, die, family in cases:
            platform = Xilinx7SeriesPlatform(device, [], toolchain="openxc7")
            platform.toolchain.platform = platform
            platform.toolchain._check_properties()

            self.assertEqual(platform.toolchain.openxc7_part,   part)
            self.assertEqual(platform.toolchain.openxc7_dbpart, dbpart)
            self.assertEqual(platform.toolchain.openxc7_die,    die)
            self.assertEqual(platform.toolchain._xc7family,     family)

    @unittest.skipIf(os.name == "nt", "POSIX shell required")
    def test_openxc7_generated_script_runs_with_current_commands(self):
        platform = Xilinx7SeriesPlatform("xc7k325t-ffg900-2", [], toolchain="openxc7")

        with tempfile.TemporaryDirectory() as tmp_dir:
            stubs = os.path.join(tmp_dir, "bin")
            os.makedirs(stubs)
            for name in ("yosys", "nextpnr-xilinx", "fasm2frames", "xc7frames2bit"):
                stub = os.path.join(stubs, name)
                with open(stub, "w") as f:
                    f.write("#!/bin/sh\nexit 0\n")
                os.chmod(stub, 0o755)

            env = _clear_openxc7_env()
            env.update({
                "CHIPDB":         os.path.join(tmp_dir, "chipdb"),
                "PRJXRAY_DB_DIR": os.path.join(tmp_dir, "prjxray-db"),
            })
            with mock.patch.dict(os.environ, env):
                with mock.patch("litex.build.xilinx.yosys_nextpnr.which", return_value=None):
                    with mock.patch("litex.build.xilinx.yosys_nextpnr._openxc7_prefix",
                            return_value=os.path.join(tmp_dir, "prefix")):
                        platform.build(_MinimalSoC(), build_dir=tmp_dir, build_name="top", run=False)

            script = os.path.join(tmp_dir, "build_top.sh")
            result = subprocess.run(["/bin/bash", script], cwd=tmp_dir, capture_output=True, text=True,
                env = {
                    "PATH":           stubs,
                    "CHIPDB":         env["CHIPDB"],
                    "PRJXRAY_DB_DIR": env["PRJXRAY_DB_DIR"],
                })

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
