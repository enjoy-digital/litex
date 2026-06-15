#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import tempfile
import unittest
from pathlib import Path

from litex.soc.software.demo import demo


class TestBareMetalDemo(unittest.TestCase):
    def _linker_with_regions(self, mem="main_ram", runtime_mem="sram"):
        src = Path(demo.__file__).with_name("linker.ld")
        with tempfile.TemporaryDirectory() as tmpdir:
            dst = Path(tmpdir) / "linker.ld"
            dst.write_text(src.read_text())
            demo._update_linker_regions(dst, mem=mem, runtime_mem=runtime_mem)
            return dst.read_text()

    def test_default_regions(self):
        linker = self._linker_with_regions()
        self.assertIn("} > main_ram\n", linker)
        self.assertIn("} > sram AT > main_ram\n", linker)
        self.assertIn("} > sram\n", linker)
        self.assertIn("PROVIDE(_fstack = ORIGIN(sram) + LENGTH(sram));", linker)

    def test_runtime_sections_can_use_main_ram(self):
        linker = self._linker_with_regions(runtime_mem="main_ram")
        self.assertIn("} > main_ram AT > main_ram\n", linker)
        self.assertIn("PROVIDE(_fstack = ORIGIN(main_ram) + LENGTH(main_ram));", linker)
        self.assertNotIn("} > sram", linker)

    def test_rom_code_keeps_sram_runtime_by_default(self):
        linker = self._linker_with_regions(mem="rom")
        self.assertIn("} > rom\n", linker)
        self.assertIn("} > sram AT > rom\n", linker)
        self.assertIn("PROVIDE(_fstack = ORIGIN(sram) + LENGTH(sram));", linker)

    def test_memory_names_can_overlap(self):
        linker = self._linker_with_regions(mem="sram", runtime_mem="main_ram")
        self.assertIn("} > sram\n", linker)
        self.assertIn("} > main_ram AT > sram\n", linker)
        self.assertIn("PROVIDE(_fstack = ORIGIN(main_ram) + LENGTH(main_ram));", linker)


if __name__ == "__main__":
    unittest.main()
