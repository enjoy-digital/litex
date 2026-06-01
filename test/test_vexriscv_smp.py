#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import tempfile
import unittest

from types import SimpleNamespace
from unittest.mock import patch

from litex.soc.cores.cpu.vexriscv_smp.core import VexRiscvSMP


class _FakePlatform:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.sources    = []

    def add_source(self, filename, language=None, library=None, copy=False):
        self.sources.append((filename, language, library, copy))


class TestVexRiscvSMP(unittest.TestCase):
    def test_add_sources_copies_cluster_to_build_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vdir       = os.path.join(tmpdir, "pythondata")
            output_dir = os.path.join(tmpdir, "build")
            os.makedirs(vdir)
            os.makedirs(output_dir)

            ram_filename     = "Ram_1w_1rs_Generic.v"
            cluster_filename = "VexRiscvLitexSmpCluster_Test.v"
            ram_path         = os.path.join(vdir, ram_filename)
            cluster_path     = os.path.join(vdir, cluster_filename)

            with open(ram_path, "w") as f:
                f.write("module ram(); endmodule\n")
            with open(cluster_path, "w") as f:
                f.write("module VexRiscvLitexSmpCluster_Test(); endmodule\n")
            os.chmod(cluster_path, 0o444)

            cpu = object.__new__(VexRiscvSMP)
            cpu.cluster_name = "VexRiscvLitexSmpCluster_Test"
            platform = _FakePlatform(output_dir)

            with patch("litex.soc.cores.cpu.vexriscv_smp.core.get_data_mod",
                       return_value=SimpleNamespace(data_location=vdir)):
                with patch("litex.soc.cores.cpu.vexriscv_smp.core.get_cpu_ram_filename",
                           return_value=ram_filename):
                    cpu.add_sources(platform)

            build_cluster_path = os.path.join(output_dir, "gateware", cluster_filename)
            with open(cluster_path) as f:
                self.assertEqual(f.read(), "module VexRiscvLitexSmpCluster_Test(); endmodule\n")
            with open(build_cluster_path) as f:
                self.assertEqual(
                    f.read(),
                    "`define SYNTHESIS\nmodule VexRiscvLitexSmpCluster_Test(); endmodule\n")

            self.assertIn((ram_path, "verilog", None, False), platform.sources)
            self.assertIn((build_cluster_path, "verilog", None, False), platform.sources)


if __name__ == "__main__":
    unittest.main()
