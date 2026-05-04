#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.tools.litex_wishbone_burst_benchmark import parse_litex_sim_output


class TestWishboneBurstBenchmarkTool(unittest.TestCase):
    def test_parse_litex_sim_output(self):
        output = """
  Write speed: 1.6MiB/s
--====== Wishbone Burst Benchmark ======--
   Read speed: 542.3KiB/s
wishbone_burst_monitor main_ram cycles=100 beats=24 burst_count=3 burst_beats=24 max_burst_beats=8 orphan_end=0 unsupported_bte=0
wishbone_burst_monitor l2_slave cycles=200 beats=1024 burst_count=512 burst_beats=1024 max_burst_beats=2 orphan_end=0 unsupported_bte=0
"""
        result = parse_litex_sim_output(output)

        self.assertEqual(result["write_speed"], "")
        self.assertEqual(result["write_speed_Bps"], "")
        self.assertEqual(result["read_speed"], "542.3KiB/s")
        self.assertEqual(result["read_speed_Bps"], 555315)
        self.assertEqual(result["monitors"]["main_ram"]["max_burst_beats"], 8)
        self.assertEqual(result["monitors"]["l2_slave"]["burst_count"], 512)

    def test_parse_without_benchmark_marker(self):
        output = """
  Write speed: 1.6MiB/s
   Read speed: 542.3KiB/s
"""
        result = parse_litex_sim_output(output)

        self.assertEqual(result["write_speed"], "1.6MiB/s")
        self.assertEqual(result["read_speed"], "542.3KiB/s")


if __name__ == "__main__":
    unittest.main()
