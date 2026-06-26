#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import Module

from litex.build.sim.platform import SimPlatform


def _reset_value(signal):
    reset = signal.reset
    if hasattr(reset, "value"):
        reset = reset.value
    return int(reset)


class TestSimPlatform(unittest.TestCase):
    def test_trace_is_enabled_by_default(self):
        platform = SimPlatform("SIM", [])
        self.assertEqual(_reset_value(platform.trace), 1)

    def test_add_debug_uses_requested_trace_reset(self):
        platform = SimPlatform("SIM", [])
        dut = Module()

        platform.add_debug(dut, reset=0)

        self.assertIsNone(platform.trace)
        self.assertEqual(_reset_value(dut.sim_trace.enable.storage), 0)


if __name__ == "__main__":
    unittest.main()
