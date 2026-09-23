import io
import unittest
from contextlib import redirect_stdout

from litex.tools.litex_json2dts_zephyr import _overlay_handlers, cpu_handler, generate_dts_config

SYS_CLK_FREQ = 100_000_000
CPU_CLK_FREQ = 800_000_000


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
            "config_clock_frequency": SYS_CLK_FREQ,
            "config_csr_data_width": 32,
        },
        "memories": {},
    }


class TestLiteXJson2DTSZephyr(unittest.TestCase):
    def test_cpu_node_uses_sys_clk_freq_without_system_clock_node_ref(self):
        csr = csr_with_i2c_instances()
        csr["constants"]["config_cpu_clk_freq"] = CPU_CLK_FREQ
        self.assertEqual(cpu_handler("cpu", {}, csr).strip(),
            "clock-frequency = <{}>;".format(SYS_CLK_FREQ))

    def test_cpu_node_uses_cpu_clk_freq_with_system_clock_node_ref(self):
        csr = csr_with_i2c_instances()
        csr["constants"]["config_cpu_system_clock_node_ref"] = "clk_sys"
        csr["constants"]["config_cpu_clk_freq"] = CPU_CLK_FREQ
        self.assertEqual(cpu_handler("cpu", {}, csr).strip(),
            "clock-frequency = <{}>;".format(CPU_CLK_FREQ))

    def test_cpu_node_falls_back_to_sys_clk_freq_without_cpu_clk_freq(self):
        csr = csr_with_i2c_instances()
        csr["constants"]["config_cpu_system_clock_node_ref"] = "clk_sys"
        self.assertEqual(cpu_handler("cpu", {}, csr).strip(),
            "clock-frequency = <{}>;".format(SYS_CLK_FREQ))

    def test_cpu_and_system_clock_frequencies_in_both_output_modes(self):
        csr = csr_with_i2c_instances()
        csr["constants"].update({
            "config_cpu_clk_freq": CPU_CLK_FREQ,
            "config_cpu_system_clock_node_ref": "ae350_clk",
        })

        for generate_soc_nodes in (False, True):
            with self.subTest(generate_soc_nodes=generate_soc_nodes):
                with redirect_stdout(io.StringIO()):
                    dts, _ = generate_dts_config(
                        csr,
                        _overlay_handlers,
                        generate_soc_nodes=generate_soc_nodes,
                    )

                dts = " ".join(dts.split())
                self.assertIn(
                    "&cpu0 {{ clock-frequency = <{}>; }};".format(CPU_CLK_FREQ), dts)
                self.assertIn(
                    "&ae350_clk {{ clock-frequency = <{}>; }};".format(SYS_CLK_FREQ), dts)

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
