#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.tools.litex_json2dts_linux import generate_dts, generate_dts_sdcard


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
    def riscv_soc(self):
        return {
            "constants": {
                "config_platform_name":   "test",
                "config_cpu_name":        "gowin_ae350",
                "config_cpu_family":      "riscv",
                "config_cpu_isa":         "rv32imafdc",
                "config_cpu_mmu":         "sv32",
                "config_clock_frequency": 50_000_000,
                "config_cpu_clk_freq":    800_000_000,
                "config_cpu_plic_ndev":   27,
                "ethmac_rx_slots":        2,
                "ethmac_tx_slots":        2,
                "ethmac_slot_size":       2048,
            },
            "csr_bases": {
                "ctrl":   0xe800_0000,
                "uart":   0xe800_0800,
                "ethphy": 0xe800_1000,
                "ethmac": 0xe800_1800,
            },
            "memories": {
                "main_ram": {"base": 0x4000_0000, "size": 0x4000_0000},
                "plic":     {"base": 0xe400_0000, "size": 0x40_0000},
                "plmt":     {"base": 0xe600_0000, "size": 0x1000},
                "ethmac":   {"base": 0xe801_0000, "size": 0x2000},
            },
        }

    def test_ae350_internal_timer_and_polling_peripherals(self):
        dts = generate_dts(self.riscv_soc())
        self.assertIn('compatible = "andestech,plmt0";', dts)
        self.assertIn("reg = <0xe6000000 0x1000>;", dts)
        self.assertIn("&L0 7>", dts)
        self.assertIn("riscv,ndev = <27>;", dts)
        self.assertIn("timebase-frequency = <50000000>;", dts)
        self.assertIn("clock-frequency = <800000000>;", dts)
        self.assertNotIn("interrupts =", dts)

    def test_riscv_existing_interrupt_and_clock_defaults(self):
        soc = self.riscv_soc()
        soc["constants"].update(config_cpu_name="vexriscv_smp", uart_interrupt=2, ethmac_interrupt=3)
        del soc["constants"]["config_cpu_clk_freq"]
        del soc["constants"]["config_cpu_plic_ndev"]
        del soc["memories"]["plmt"]
        dts = generate_dts(soc)
        self.assertIn("riscv,ndev = <32>;", dts)
        self.assertIn("clock-frequency = <50000000>;", dts)
        self.assertIn("interrupts = <2>;", dts)
        self.assertIn("interrupts = <3>;", dts)
        self.assertNotIn("andestech,plmt0", dts)

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
