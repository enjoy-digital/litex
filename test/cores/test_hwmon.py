#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from litex.soc.cores.hwmon import (
    GowinAroraVTemperatureSensor,
    IntelA10C10GXTemperatureSensor,
    IntelLegacyTemperatureSensor,
)
from litex.tools.litex_json2dts_linux import generate_dts_hwmon_temperature


def get_constants(core):
    return {constant.name: constant.constant for constant in core.get_constants()}


class TestHwmon(unittest.TestCase):
    def test_gowin_arora_v_hwmon_constants(self):
        constants = get_constants(GowinAroraVTemperatureSensor())

        self.assertEqual(constants["hwmon_temp_scale"],       250)
        self.assertEqual(constants["hwmon_temp_divisor"],     1)
        self.assertEqual(constants["hwmon_temp_offset"],      0)
        self.assertEqual(constants["hwmon_temp_signed_bits"], 14)

    def test_intel_hwmon_constants(self):
        constants = get_constants(IntelA10C10GXTemperatureSensor())

        self.assertEqual(constants["hwmon_temp_scale"],       693000)
        self.assertEqual(constants["hwmon_temp_divisor"],     1024)
        self.assertEqual(constants["hwmon_temp_offset"],      265000)
        self.assertEqual(constants["hwmon_temp_signed_bits"], 0)

    def test_intel_legacy_hwmon_constants(self):
        constants = get_constants(IntelLegacyTemperatureSensor())

        self.assertEqual(constants["hwmon_temp_scale"],       1000)
        self.assertEqual(constants["hwmon_temp_divisor"],     1)
        self.assertEqual(constants["hwmon_temp_offset"],      128000)
        self.assertEqual(constants["hwmon_temp_signed_bits"], 0)

    def test_dts_gowin_temperature_sensor(self):
        dts = generate_dts_hwmon_temperature({
            "csr_bases": {
                "fpga_temp": 0xf0005000,
            },
            "csr_registers": {
                "fpga_temp_temperature": {"addr": 0xf0005004, "size": 1, "type": "ro"},
            },
            "constants": {
                "config_csr_data_width": 32,
            },
            "cores": {
                "fpga_temp": "GowinAroraVTemperatureSensor",
            },
        })

        self.assertIn('compatible = "litex,hwmon-gowin-arora-v", "litex,hwmon-temp";', dts)
        self.assertIn("reg = <0xf0005000 0x8>;", dts)
        self.assertIn("litex,temperature-csr-offset = <0x4>;", dts)
        self.assertIn("litex,temperature-mul = <250>;", dts)
        self.assertIn("litex,temperature-div = <1>;", dts)
        self.assertIn("litex,temperature-offset = <0>;", dts)
        self.assertIn("litex,temperature-signed-bits = <14>;", dts)

    def test_dts_intel_temperature_sensor(self):
        dts = generate_dts_hwmon_temperature({
            "csr_bases": {
                "fpga_temp": 0xf0005000,
            },
            "constants": {},
            "cores": {
                "fpga_temp": "IntelA10C10GXTemperatureSensor",
            },
        })

        self.assertIn(
            'compatible = "litex,hwmon-intel-a10-c10gx", "litex,hwmon-intel-temp", "litex,hwmon-temp";',
            dts,
        )
        self.assertIn("litex,temperature-mul = <693000>;", dts)
        self.assertIn("litex,temperature-div = <1024>;", dts)
        self.assertIn("litex,temperature-offset = <265000>;", dts)
        self.assertNotIn("litex,temperature-signed-bits", dts)


if __name__ == "__main__":
    unittest.main()
