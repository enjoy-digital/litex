#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.watchdog import Watchdog


# Control register bit offsets (mirror Watchdog._control fields).
FEED   = 1 << 0
ENABLE = 1 << 8


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


if __name__ == "__main__":
    unittest.main()
