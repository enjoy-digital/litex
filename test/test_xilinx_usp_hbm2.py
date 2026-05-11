#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.cores.ram.xilinx_usp_hbm2 import (
    USPHBM2_HIGH_BASE,
    USPHBM2_CHANNEL_SIZE,
    parse_usphbm2_channels,
    usphbm2_channel_origin,
    usphbm2_channel_origins,
    usphbm2_window_end,
)

# Tests --------------------------------------------------------------------------------------------

class TestUSPHBM2Helpers(unittest.TestCase):
    def test_channel_parser_accepts_lists_ranges_and_all(self):
        self.assertEqual(parse_usphbm2_channels("0,1,2,3"), (0, 1, 2, 3))
        self.assertEqual(parse_usphbm2_channels("0-3,8"), (0, 1, 2, 3, 8))
        self.assertEqual(parse_usphbm2_channels("all"), tuple(range(32)))

    def test_channel_parser_rejects_invalid_channels(self):
        for channels in ["", "3-1", "0,0", "32"]:
            with self.subTest(channels=channels):
                with self.assertRaises(ValueError):
                    parse_usphbm2_channels(channels)

    def test_channel_origin_map_keeps_low_window_and_moves_upper_channels_high(self):
        self.assertEqual(usphbm2_channel_origin(0), 0x4000_0000)
        self.assertEqual(usphbm2_channel_origin(3), 0x7000_0000)
        self.assertEqual(usphbm2_channel_origin(4), USPHBM2_HIGH_BASE)

    def test_window_end_reports_selected_channel_limit(self):
        origins = usphbm2_channel_origins((0, 1, 4))
        self.assertEqual(usphbm2_window_end(origins), USPHBM2_HIGH_BASE + USPHBM2_CHANNEL_SIZE)


if __name__ == "__main__":
    unittest.main()
