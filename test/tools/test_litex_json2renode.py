#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import io
import unittest
from contextlib import redirect_stdout

from litex.tools.litex_json2renode import (
    filter_memory_regions,
    generate_cpu,
    generate_memory_region,
    generate_sysbus_registration,
    generate_video_framebuffer,
)


class TestLiteXJson2Renode(unittest.TestCase):
    def test_sysbus_registration_can_emit_named_shadow_region(self):
        registration = generate_sysbus_registration({
            "base":             0x1000,
            "shadowed_address": 0x2000,
            "size":             0x100,
        }, skip_braces=True, region="csr")

        self.assertIn('address: 0x1000', registration)
        self.assertIn('address: 0x2000', registration)
        self.assertIn('size: 0x100', registration)
        self.assertEqual(registration.count('region: "csr"'), 2)

    def test_memory_region_reports_autoaligned_metadata(self):
        repl = generate_memory_region({
            "name":             "rom",
            "base":             0x00000000,
            "size":             0x1000,
            "original_address": 0x00000010,
            "original_size":    0x0f00,
        })

        self.assertIn("rom: Memory.MappedMemory", repl)
        self.assertIn("original base address", repl)
        self.assertIn("0x10", repl)
        self.assertIn("original size", repl)
        self.assertIn("0xf00", repl)

    def test_filter_memory_regions_autoaligns_base_and_size(self):
        with redirect_stdout(io.StringIO()):
            regions = list(filter_memory_regions([{
                "name": "sram",
                "base": 0x1004,
                "size": 0x1800,
                "type": "cached",
            }], alignment=0x1000, autoalign=["sram"]))

        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["base"], 0x1000)
        self.assertEqual(regions[0]["size"], 0x2000)
        self.assertEqual(regions[0]["original_address"], 0x1004)
        self.assertEqual(regions[0]["original_size"], 0x1800)

    def test_generate_cpu_uses_variant_and_time_provider_for_each_core(self):
        repl = generate_cpu({
            "constants": {
                "config_cpu_type_vexriscv":    None,
                "config_cpu_variant_standard": None,
            },
        }, time_provider="clint", number_of_cores=2)

        self.assertIn("cpu0: CPU.VexRiscv", repl)
        self.assertIn("cpu1: CPU.VexRiscv", repl)
        self.assertEqual(repl.count('cpuType: "rv32im_zicsr_zifencei"'), 2)
        self.assertEqual(repl.count("timeProvider: clint"), 2)

    def test_generate_video_framebuffer_uses_containing_memory_region(self):
        repl = generate_video_framebuffer({
            "csr_bases": {
                "video_framebuffer":     0xf0005000,
                "video_framebuffer_vtg": 0xf0006000,
            },
            "constants": {
                "video_framebuffer_hres": 640,
                "video_framebuffer_vres": 480,
                "video_framebuffer_base": 0x40002000,
            },
            "filtered_memories": [{
                "name": "main_ram",
                "base": 0x40000000,
                "size": 0x01000000,
            }],
        }, "video_framebuffer")

        self.assertIn("litex_video: Video.LiteX_Framebuffer_CSR32", repl)
        self.assertIn("memory: main_ram", repl)
        self.assertIn("offset: 0x00002000", repl)
        self.assertIn("hres: 640", repl)
        self.assertIn("vres: 480", repl)


if __name__ == "__main__":
    unittest.main()
