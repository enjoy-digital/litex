#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import run_simulation

from litex.soc.cores.jtag import JTAGBitbang


class TestJTAGBitbang(unittest.TestCase):
    def test_idle_pins_scan_control_and_tdo(self):
        dut = JTAGBitbang()

        def check():
            yield
            self.assertEqual((yield dut.tck), 0)
            self.assertEqual((yield dut.tms), 1)
            self.assertEqual((yield dut.tdi), 0)
            self.assertEqual((yield dut.trst), 1)
            for value in range(16):
                yield from dut._control.write(value)
                yield
                yield
                for bit, pin in enumerate([dut.tck, dut.tms, dut.tdi, dut.trst]):
                    self.assertEqual((yield pin), (value >> bit) & 1)
            for value in [1, 0]:
                yield dut.tdo.eq(value)
                for _ in range(4):
                    yield
                self.assertEqual((yield dut._status.fields.tdo), value)

        run_simulation(dut, check())
