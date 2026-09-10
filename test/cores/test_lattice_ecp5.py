#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import ClockDomain, Signal

from litex.soc.cores.clock.lattice_ecp5 import ECP5PLL


class TestECP5PLL(unittest.TestCase):
    def test_configuration_queries_leave_outputs_unchanged(self):
        pll = ECP5PLL()
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("sys"), 80e6)
        pll.expose_dpa()
        outputs = dict(pll.clkouts)
        first = pll.compute_config()
        self.assertEqual(pll.clkouts, outputs)
        self.assertEqual(pll.compute_config(), first)
        self.assertEqual(pll.clkouts, outputs)
        self.assertEqual(first["clkfb"], 1)
        pll.get_fragment()
        self.assertEqual(pll.clkouts, outputs)
        self.assertEqual(pll.params["p_FEEDBK_PATH"], "INT_OS")
        self.assertEqual(pll.params["p_CLKOS_DIV"], first["clko1_div"])

    def test_can_add_output_after_configuration_query(self):
        pll = ECP5PLL()
        pll.register_clkin(Signal(), 100e6)
        pll.create_clkout(ClockDomain("sys"), 80e6)
        pll.expose_dpa()
        pll.compute_config()
        pll.create_clkout(ClockDomain("other"), 40e6)
        config = pll.compute_config()
        self.assertEqual(set(pll.clkouts), {0, 1})
        self.assertEqual(config["clkfb"], 2)
        pll.get_fragment()
        self.assertEqual(pll.params["p_FEEDBK_PATH"], "INT_OS2")

    def test_four_outputs_reuse_eligible_feedback(self):
        pll = ECP5PLL()
        pll.register_clkin(Signal(), 100e6)
        for n in range(4):
            pll.create_clkout(ClockDomain("out" + str(n)), 200e6, uses_dpa=(n != 0))
        pll.expose_dpa()
        config = pll.compute_config()
        self.assertEqual(config["clkfb"], 0)
        self.assertEqual(set(pll.clkouts), {0, 1, 2, 3})
        pll.get_fragment()
        self.assertEqual(pll.params["p_FEEDBK_PATH"], "INT_OP")

    def test_four_dynamic_outputs_have_no_spare_feedback(self):
        pll = ECP5PLL()
        pll.register_clkin(Signal(), 100e6)
        for n in range(4):
            pll.create_clkout(ClockDomain("out" + str(n)), 200e6)
        pll.expose_dpa()
        with self.assertRaisesRegex(ValueError, "No PLL config"):
            pll.compute_config()
        self.assertEqual(set(pll.clkouts), {0, 1, 2, 3})
