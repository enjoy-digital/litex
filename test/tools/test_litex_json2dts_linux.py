#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.tools.litex_json2dts_linux import generate_dts_sdcard


def csr_with_sdcard(constants=None):
    constants = {} if constants is None else dict(constants)
    constants.setdefault("sdcard_interrupt", 2)

    return {
        "csr_bases": {
            "sdcard": 0xf0002000,
        },
        "csr_registers": {
            "sdcard_phy_card_detect":    {"addr": 0xf0002000, "size": 1, "type": "ro"},
            "sdcard_core_cmd_argument":  {"addr": 0xf0002100, "size": 1, "type": "rw"},
            "sdcard_block2mem_dma_base": {"addr": 0xf0002200, "size": 2, "type": "rw"},
            "sdcard_mem2block_dma_base": {"addr": 0xf0002300, "size": 2, "type": "rw"},
            "sdcard_ev_status":          {"addr": 0xf0002400, "size": 1, "type": "ro"},
        },
        "constants": constants,
        "memories": {},
    }


class TestLiteXJson2DTSLinux(unittest.TestCase):
    def test_sdcard_defaults_to_big_csr_ordering(self):
        dts = generate_dts_sdcard(csr_with_sdcard())

        self.assertIn('compatible = "litex,mmc";', dts)
        self.assertIn("big-endian;", dts)
        self.assertNotIn("little-endian;", dts)

    def test_sdcard_uses_little_csr_ordering(self):
        dts = generate_dts_sdcard(csr_with_sdcard({
            "config_csr_ordering_little": None,
        }))

        self.assertIn("little-endian;", dts)
        self.assertNotIn("big-endian;", dts)

    def test_sdcard_rejects_conflicting_csr_ordering(self):
        with self.assertRaises(ValueError):
            generate_dts_sdcard(csr_with_sdcard({
                "config_csr_ordering_big":    None,
                "config_csr_ordering_little": None,
            }))


if __name__ == "__main__":
    unittest.main()
