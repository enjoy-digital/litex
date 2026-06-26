import io
import unittest
from contextlib import redirect_stdout

from litex.tools.litex_json2dts_zephyr import _overlay_handlers, generate_dts_config


def csr_with_i2c_instances():
    return {
        "csr_bases": {
            "i2c0": 0xe0004000,
            "i2c2": 0xe0005000,
        },
        "csr_registers": {
            "i2c0_w": {
                "addr": 0xe0004000,
                "size": 1,
                "type": "rw",
            },
            "i2c0_r": {
                "addr": 0xe0004004,
                "size": 1,
                "type": "ro",
            },
            "i2c2_w": {
                "addr": 0xe0005000,
                "size": 1,
                "type": "rw",
            },
            "i2c2_r": {
                "addr": 0xe0005004,
                "size": 1,
                "type": "ro",
            },
        },
        "constants": {
            "config_clock_frequency": 100000000,
            "config_csr_data_width": 32,
        },
        "memories": {},
    }


class TestLiteXJson2DTSZephyr(unittest.TestCase):
    def test_overlay_mode_keeps_fixed_handler_behavior(self):
        with redirect_stdout(io.StringIO()) as output:
            dts, config = generate_dts_config(csr_with_i2c_instances(), _overlay_handlers)

        self.assertIn("&i2c0", dts)
        self.assertNotIn("i2c2: i2c@e0005000", dts)
        self.assertIn("No overlay handler for: i2c2", output.getvalue())
        self.assertEqual(config, "")

    def test_soc_node_mode_generates_multiple_i2c_instances(self):
        with redirect_stdout(io.StringIO()) as output:
            dts, config = generate_dts_config(
                csr_with_i2c_instances(),
                _overlay_handlers,
                generate_soc_nodes=True,
            )

        self.assertNotIn("&i2c0", dts)
        self.assertIn('compatible = "simple-bus";', dts)
        self.assertIn("ranges;", dts)
        self.assertIn("i2c0: i2c@e0004000 {", dts)
        self.assertIn("i2c2: i2c@e0005000 {", dts)
        self.assertEqual(dts.count('compatible = "litex,i2c";'), 2)
        self.assertEqual(dts.count("clock-frequency = <100000>;"), 2)
        self.assertIn('reg-names = "write",', dts)
        self.assertNotIn("No SoC node handler for: i2c2", output.getvalue())
        self.assertEqual(config, "")


if __name__ == "__main__":
    unittest.main()
