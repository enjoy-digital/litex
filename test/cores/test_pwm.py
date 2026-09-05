#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.cores.pwm import PWM, MultiChannelPWM


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
    def test_csr_synchronizer_destination(self):
        for clock_domain in ["sys", "pwm"]:
            with self.subTest(clock_domain=clock_domain):
                dut = PWM(clock_domain=clock_domain)
                regs = [s for s in dut.get_fragment().specials if isinstance(s, MultiReg)]
                self.assertEqual(len(regs), 3)
                self.assertTrue(all(s.odomain == clock_domain for s in regs))
                self.assertTrue(all(s.n == (0 if clock_domain == "sys" else 2) for s in regs))

    def test_csr_updates_in_pwm_domain(self):
        dut = PWM(clock_domain="pwm")

        def write_csrs():
            # Before the first PWM edge, many sys edges must not update PWM controls.
            yield dut._width.storage.eq(3)
            yield dut._period.storage.eq(8)
            yield dut._enable.storage.eq(1)
            for _ in range(8):
                yield
                self.assertEqual((yield dut.enable), 0)
                self.assertEqual((yield dut.width), 0)
                self.assertEqual((yield dut.period), 0)

        def check_pwm():
            for _ in range(5):
                yield
            self.assertEqual((yield dut.enable), 1)
            self.assertEqual((yield dut.width), 3)
            self.assertEqual((yield dut.period), 8)
            high = 0
            for _ in range(32):
                high += (yield dut.pwm)
                yield
            self.assertEqual(high, 12)

        run_simulation(dut, {"sys": write_csrs(), "pwm": check_pwm()},
                       clocks={"sys": 10, "pwm": (200, 100)})

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

    def test_dynamic_duty_change(self):
        # Width updates while the PWM is enabled must take effect — count high cycles in a
        # window before the change and another after the change, and assert each window matches
        # its own configured duty.
        dut = PWM(with_csr=False)
        period = 8

        def gen():
            yield dut.period.eq(period)
            yield dut.enable.eq(1)
            yield dut.width.eq(2)
            for _ in range(4):
                yield  # let things settle
            high1 = 0
            for _ in range(period*4):
                yield
                if (yield dut.pwm):
                    high1 += 1
            self.assertEqual(high1, 2*4)

            yield dut.width.eq(6)
            for _ in range(4):
                yield  # settle the width change
            high2 = 0
            for _ in range(period*4):
                yield
                if (yield dut.pwm):
                    high2 += 1
            self.assertEqual(high2, 6*4)
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


class TestMultiChannelPWM(unittest.TestCase):
    def test_independent_enables(self):
        for clock_domain in ["sys", "pwm"]:
            with self.subTest(clock_domain=clock_domain):
                pads = Signal(3)
                dut = MultiChannelPWM(pads, clock_domain=clock_domain)
                channels = [dut.channel0, dut.channel1, dut.channel2]

                def gen():
                    yield dut.channel0._period.storage.eq(8)
                    for channel, width in zip(channels, [1, 2, 3]):
                        yield channel._width.storage.eq(width)
                    # Disable channel 0 while keeping other channels active, then re-enable it.
                    for mask in [1, 2, 4, 3, 6, 7, 0, 2, 1]:
                        for n, channel in enumerate(channels):
                            yield channel._enable.storage.eq((mask >> n) & 1)
                        for _ in range(8):
                            yield
                        high = [0, 0, 0]
                        for _ in range(32):
                            for n in range(3):
                                high[n] += (yield pads[n])
                            yield
                        self.assertEqual(high, [4*(n + 1) if mask & (1 << n) else 0
                                                for n in range(3)])

                run_simulation(dut, {clock_domain: gen()}, clocks={"sys": 10, "pwm": 14})


if __name__ == "__main__":
    unittest.main()
