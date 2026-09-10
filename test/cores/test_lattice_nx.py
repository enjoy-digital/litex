#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from unittest.mock import Mock, patch

from migen import ClockDomain, Signal

from litex.soc.cores.clock.lattice_nx import NXPLL


class TestNXPLL(unittest.TestCase):
    def test_reference_and_pfd_limits(self):
        pll = NXPLL()
        with self.assertRaisesRegex(ValueError, "Input clock frequency"):
            pll.register_clkin(Signal(), 17e6)
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("sys"), 74.25e6)
        config = pll.compute_config()
        self.assertGreaterEqual(100e6/config["clki_div"], 18e6)
        self.assertLessEqual(100e6/config["clki_div"], 500e6)
        self.assertLessEqual(abs(config["clko0_freq"]/74.25e6 - 1), 1e-2)

    def test_emitted_input_divider(self):
        for frequency, divider in ((200e6, 1), (310e6, 2), (74.25e6, 5)):
            with self.subTest(frequency=frequency):
                pll = NXPLL()
                pll.register_clkin(Signal(), 100e6)
                pll.create_clkout(ClockDomain("sys"), frequency)
                config = pll.compute_config()
                self.assertEqual(config["clki_div"], divider)
                with patch.object(pll, "calculate_analog_parameters", wraps=pll.calculate_analog_parameters) as analog:
                    pll.get_fragment()
                    analog.assert_called_once_with(100e6/divider, config["clkfb_div"])
                reference_div = int(pll.params["p_REF_MMD_DIG"])
                feedback_div  = int(pll.params["p_DIVF"]) + 1
                output_div    = int(pll.params["p_DIVA"]) + 1
                actual = 100e6/reference_div*feedback_div/output_div
                self.assertAlmostEqual(actual, config["clko0_freq"])
                self.assertEqual(pll.params["p_REF_MMD_PULS_CTL"], "0b0000" if divider <= 2 else "0b0001")

    def test_output_constraint_uses_actual_frequency(self):
        platform = Mock()
        pll = NXPLL(platform=platform, create_output_port_clocks=True, name="sys_pll")
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("sys"), 74.25e6)
        config = pll.compute_config()
        self.assertNotEqual(config["clko0_freq"], 74.25e6)
        pll.get_fragment()
        command = platform.add_platform_command.call_args.args[0]
        period = float(command.split("-period ", 1)[1].split()[0])
        self.assertAlmostEqual(1e9/period, config["clko0_freq"])

    def test_analog_bandwidth_uses_hz(self):
        pll = NXPLL()
        for reference, feedback in ((20e6, 78), (18e6, 88)):
            with self.subTest(reference=reference):
                selected = pll.calculate_analog_parameters(reference, feedback, bw_factor=5)
                candidate = next(p for p in pll.transfer_func_coefficients
                    if {"p_" + key: value for key, value in pll.numerical_params_to_HDL_params(p).items()} == selected)
                bandwidth = pll.closed_loop_3db(feedback, candidate)["f"]
                self.assertGreaterEqual(reference/bandwidth, 5)
        with self.assertRaisesRegex(ValueError, "No PLL analog parameters"):
            pll.calculate_analog_parameters(20e6, 78, bw_factor=1e6)
