#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.pwm import PWM


def sample_pwm(dut, cycles):
    """Sample dut.pwm for `cycles` clock cycles. Returns list of 0/1 values."""
    samples = []
    def gen():
        for _ in range(cycles):
            yield
            samples.append((yield dut.pwm))
    run_simulation(dut, gen())
    return samples


class TestPWM(unittest.TestCase):
    def test_disabled_stays_low(self):
        dut = PWM(with_csr=False)
        def gen():
            yield dut.width.eq(4)
            yield dut.period.eq(8)
            yield dut.enable.eq(0)
            for _ in range(32):
                yield
                self.assertEqual((yield dut.pwm), 0)
        run_simulation(dut, gen())

    def test_duty_cycle(self):
        # Enabled with width=3, period=8 → expect 3 high cycles per 8-cycle period.
        dut = PWM(with_csr=False)
        width, period, nperiods = 3, 8, 5

        def gen():
            yield dut.width.eq(width)
            yield dut.period.eq(period)
            yield dut.enable.eq(1)
            # Discard a few cycles so the sync assignments settle.
            for _ in range(4):
                yield
            high = 0
            for _ in range(period*nperiods):
                yield
                if (yield dut.pwm):
                    high += 1
            self.assertEqual(high, width*nperiods)
        run_simulation(dut, gen())

    def test_width_zero_stays_low(self):
        dut = PWM(with_csr=False)
        def gen():
            yield dut.width.eq(0)
            yield dut.period.eq(8)
            yield dut.enable.eq(1)
            for _ in range(32):
                yield
                self.assertEqual((yield dut.pwm), 0)
        run_simulation(dut, gen())

    def test_width_equals_period_stays_high(self):
        # Skip the first few cycles to let the sync `pwm` register settle to high.
        dut = PWM(with_csr=False)
        def gen():
            yield dut.width.eq(8)
            yield dut.period.eq(8)
            yield dut.enable.eq(1)
            for _ in range(4):
                yield
            for _ in range(32):
                yield
                self.assertEqual((yield dut.pwm), 1)
        run_simulation(dut, gen())

    def test_csr_interface(self):
        # Same duty-cycle check but driven through the CSR interface.
        dut = PWM(with_csr=True)
        width, period, nperiods = 5, 16, 4

        def gen():
            yield from dut._enable.write(0)
            yield from dut._width.write(width)
            yield from dut._period.write(period)
            yield from dut._enable.write(1)
            for _ in range(8):
                yield
            high = 0
            for _ in range(period*nperiods):
                yield
                if (yield dut.pwm):
                    high += 1
            self.assertEqual(high, width*nperiods)
        run_simulation(dut, gen())

    def test_reset_holds_counter(self):
        # Asserting `reset` freezes the counter at 0 so the duty cycle no longer scans; the
        # pwm output then becomes a constant combinational function of (enable, 0 < width).
        dut = PWM(with_csr=False)
        def gen():
            yield dut.width.eq(4)
            yield dut.period.eq(8)
            yield dut.enable.eq(1)
            yield dut.reset.eq(1)
            for _ in range(4):
                yield
            for _ in range(16):
                yield
                self.assertEqual((yield dut.counter), 0)
                self.assertEqual((yield dut.pwm), 1)  # enable & (0 < 4)
        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
