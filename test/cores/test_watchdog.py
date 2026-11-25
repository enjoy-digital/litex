#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.watchdog import Watchdog


# Control register bit offsets (mirror Watchdog._control fields).
FEED         = 1 << 0
ENABLE       = 1 << 8
RESET        = 1 << 16
PAUSE_HALTED = 1 << 24


class TestWatchdog(unittest.TestCase):
    def test_expires_after_cycles(self):
        dut = Watchdog(width=16)
        cycles_val = 20

        def gen():
            yield from dut._cycles.write(cycles_val)
            # Feed+enable: reload to `cycles_val` and start counting.
            yield from dut._control.write(ENABLE | FEED)

            ticks = 0
            while (yield dut.execute) == 0:
                ticks += 1
                self.assertLess(ticks, cycles_val + 32, "execute never asserted")
                yield
            # After execute asserts, the event must also latch.
            yield
            self.assertEqual((yield dut.ev.wdt.pending), 1)
        run_simulation(dut, gen())

    def test_feeding_keeps_quiet(self):
        dut = Watchdog(width=16)
        cycles_val = 20

        def gen():
            yield from dut._cycles.write(cycles_val)
            yield from dut._control.write(ENABLE | FEED)
            # Feed every few cycles for a duration much longer than cycles_val.
            for _ in range(4):
                for _ in range(cycles_val // 2):
                    yield
                    self.assertEqual((yield dut.execute), 0)
                yield from dut._control.write(ENABLE | FEED)
            self.assertEqual((yield dut.ev.wdt.pending), 0)
        run_simulation(dut, gen())

    def test_disabled_does_not_expire(self):
        dut = Watchdog(width=16)

        def gen():
            yield from dut._cycles.write(8)
            # Feed to preload remaining but keep enable=0.
            yield from dut._control.write(FEED)
            for _ in range(64):
                yield
                self.assertEqual((yield dut.execute), 0)
            self.assertEqual((yield dut.ev.wdt.pending), 0)
        run_simulation(dut, gen())

    def test_reload_after_expiry(self):
        dut = Watchdog(width=16)
        cycles_val = 12

        def gen():
            yield from dut._cycles.write(cycles_val)
            yield from dut._control.write(ENABLE | FEED)

            # Wait for first expiry.
            while (yield dut.execute) == 0:
                yield

            # Feed again; execute should drop once the reload propagates.
            yield from dut._control.write(ENABLE | FEED)
            timeout = 0
            while (yield dut.execute) == 1:
                timeout += 1
                self.assertLess(timeout, 16, "execute did not drop after feed")
                yield

            # And then re-expire after another full count-down.
            ticks = 0
            while (yield dut.execute) == 0:
                ticks += 1
                self.assertLess(ticks, cycles_val + 32, "did not re-expire")
                yield
        run_simulation(dut, gen())

    def test_initial_cycles_starts_at_reset(self):
        cycles_val = 20
        dut = Watchdog(width=16, initial_cycles=cycles_val)

        def gen():
            # Enabled, in reset mode and paused when halted at reset, without any CSR write.
            self.assertEqual((yield dut._control.storage), ENABLE | RESET | PAUSE_HALTED)
            self.assertEqual((yield dut._cycles.storage), cycles_val)
            ticks = 0
            while (yield dut.execute) == 0:
                ticks += 1
                self.assertLess(ticks, cycles_val + 32, "execute never asserted")
                yield
            self.assertGreaterEqual(ticks, cycles_val)
        run_simulation(dut, gen())

    def test_initial_cycles_feed_and_disable(self):
        cycles_val = 20
        dut = Watchdog(width=16, initial_cycles=cycles_val)

        def gen():
            # Feeding reloads initial_cycles and keeps it quiet.
            control = (yield dut._control.storage)
            for _ in range(4):
                for _ in range(cycles_val // 2):
                    yield
                    self.assertEqual((yield dut.execute), 0)
                yield from dut._control.write(control | FEED)
            # Disabling stops it.
            yield from dut._control.write(0)
            for _ in range(4*cycles_val):
                yield
                self.assertEqual((yield dut.execute), 0)
        run_simulation(dut, gen())

    def test_initial_cycles_default_is_disabled(self):
        dut = Watchdog(width=16)

        def gen():
            self.assertEqual((yield dut._control.storage), 0)
            for _ in range(64):
                yield
                self.assertEqual((yield dut.execute), 0)
        run_simulation(dut, gen())

    def test_initial_cycles_must_fit_width(self):
        Watchdog(width=8, initial_cycles=2**8 - 1)
        with self.assertRaises(AssertionError):
            Watchdog(width=8, initial_cycles=2**8)


if __name__ == "__main__":
    unittest.main()
