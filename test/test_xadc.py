#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.cores.xadc import S7SystemMonitor, USSystemMonitor, USPSystemMonitor
from litex.tools.litex_json2dts_linux import generate_dts_xadc


def get_constants(core):
    return {constant.name: constant.constant for constant in core.get_constants()}


class TestXADC(unittest.TestCase):
    def test_s7_hwmon_constants(self):
        constants = get_constants(S7SystemMonitor())

        self.assertEqual(constants["hwmon_temp_scale"],      503975)
        self.assertEqual(constants["hwmon_temp_divisor"],    4096)
        self.assertEqual(constants["hwmon_temp_offset"],     273150)
        self.assertEqual(constants["hwmon_voltage_scale"],   3000)
        self.assertEqual(constants["hwmon_voltage_divisor"], 4096)

    def test_us_hwmon_constants(self):
        constants = get_constants(USSystemMonitor())

        self.assertEqual(constants["hwmon_temp_scale"],      503975)
        self.assertEqual(constants["hwmon_temp_divisor"],    1024)
        self.assertEqual(constants["hwmon_temp_offset"],     273150)
        self.assertEqual(constants["hwmon_voltage_scale"],   3000)
        self.assertEqual(constants["hwmon_voltage_divisor"], 1024)

    def test_usp_hwmon_constants(self):
        constants = get_constants(USPSystemMonitor())

        self.assertEqual(constants["hwmon_temp_scale"],      507592)
        self.assertEqual(constants["hwmon_temp_divisor"],    1024)
        self.assertEqual(constants["hwmon_temp_offset"],     279427)
        self.assertEqual(constants["hwmon_voltage_scale"],   3000)
        self.assertEqual(constants["hwmon_voltage_divisor"], 1024)

    def test_dts_xadc_uses_variant_constants_and_csr_offsets(self):
        dts = generate_dts_xadc({
            "csr_bases": {
                "xadc": 0xf0003000,
            },
            "csr_registers": {
                "xadc_temperature": {"addr": 0xf0003000, "size": 1, "type": "ro"},
                "xadc_vccint":      {"addr": 0xf0003004, "size": 1, "type": "ro"},
                "xadc_vccaux":      {"addr": 0xf0003008, "size": 1, "type": "ro"},
                "xadc_vccbram":     {"addr": 0xf000300c, "size": 1, "type": "ro"},
            },
            "constants": {
                "config_csr_data_width":       32,
                "xadc_hwmon_temp_scale":       507592,
                "xadc_hwmon_temp_divisor":     1024,
                "xadc_hwmon_temp_offset":      279427,
                "xadc_hwmon_voltage_scale":    3000,
                "xadc_hwmon_voltage_divisor":  1024,
            },
            "cores": {
                "xadc": "USPSystemMonitor",
            },
        })

        self.assertIn('compatible = "litex,hwmon-xadc-usp", "litex,hwmon-xadc";', dts)
        self.assertIn("litex,temperature-csr-offset = <0x0>;", dts)
        self.assertIn("litex,vccint-csr-offset = <0x4>;", dts)
        self.assertIn("litex,vccbram-csr-offset = <0xc>;", dts)
        self.assertIn("litex,temperature-mul = <507592>;", dts)
        self.assertIn("litex,temperature-div = <1024>;", dts)
        self.assertIn("litex,temperature-offset = <279427>;", dts)
        self.assertIn("litex,voltage-div = <1024>;", dts)

    def test_dts_xadc_preserves_legacy_defaults(self):
        dts = generate_dts_xadc({
            "csr_bases": {
                "xadc": 0xf0003000,
            },
            "constants": {},
            "cores": {},
        })

        self.assertIn('compatible = "litex,hwmon-xadc";', dts)
        self.assertIn("litex,temperature-csr-offset = <0x0>;", dts)
        self.assertIn("litex,vccint-csr-offset = <0x8>;", dts)
        self.assertIn("litex,vccbram-csr-offset = <0x18>;", dts)
        self.assertIn("litex,temperature-mul = <503975>;", dts)
        self.assertIn("litex,temperature-div = <4096>;", dts)
        self.assertIn("litex,voltage-div = <4096>;", dts)


if __name__ == "__main__":
    unittest.main()
