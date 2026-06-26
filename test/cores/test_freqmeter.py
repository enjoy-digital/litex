#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.soc.cores.freqmeter import FreqMeter, _Sampler


class TestFreqMeterSampler(unittest.TestCase):
    """The _Sampler carries the arithmetic of the FreqMeter: it tracks a (possibly wrapping)
    event counter, accumulates per-cycle deltas into a 32-bit counter, and latches the total
    into the output register each time `latch` pulses. The surrounding FreqMeter is mostly CDC
    plumbing."""

    def test_linear_counter_accumulates(self):
        dut = _Sampler(width=8)
        nticks = 50

        def gen():
            # Advance `i` by one each cycle → inc should be 1 each cycle.
            for n in range(nticks):
                yield dut.i.eq((n + 1) & 0xff)
                yield
            # Latch. `o` takes the pre-edge value of `count`; the new value is visible on the
            # cycle *after* the latch edge.
            yield dut.latch.eq(1)
            yield
            yield dut.latch.eq(0)
            yield
            self.assertEqual((yield dut.o), nticks)
            # After latch, count is 0; feeding the same i for one more cycle keeps inc = 0.
            yield dut.i.eq((nticks + 1) & 0xff)
            yield
            yield dut.latch.eq(1)
            yield
            yield dut.latch.eq(0)
            yield
            self.assertEqual((yield dut.o), 1)
        run_simulation(dut, gen())

    def test_counter_wraps(self):
        # _Sampler exploits 2's-complement wrap: inc = i - i_d must behave correctly when
        # i wraps past 2**width.
        width = 6
        dut   = _Sampler(width=width)
        nticks = 200  # > 2**width so we wrap multiple times

        def gen():
            for n in range(nticks):
                yield dut.i.eq((n + 1) & ((1 << width) - 1))
                yield
            yield dut.latch.eq(1)
            yield
            yield dut.latch.eq(0)
            yield
            self.assertEqual((yield dut.o), nticks)
        run_simulation(dut, gen())

    def test_stride_greater_than_one(self):
        # Cover delta=3 per cycle to catch a hypothetical "+1 per cycle" hard-code.
        dut    = _Sampler(width=8)
        stride = 3
        nticks = 20

        def gen():
            for n in range(nticks):
                yield dut.i.eq(((n + 1)*stride) & 0xff)
                yield
            yield dut.latch.eq(1)
            yield
            yield dut.latch.eq(0)
            yield
            self.assertEqual((yield dut.o), nticks*stride)
        run_simulation(dut, gen())

    def test_periodic_latch(self):
        # Pulse `latch` repeatedly with a known number of ticks between pulses; each latch
        # window must report the count of increments in that window (and reset to 0 for the
        # next window).
        dut          = _Sampler(width=8)
        per_window   = 12
        nwindows     = 4
        seen         = []

        def gen():
            tick = 0
            for w in range(nwindows):
                for _ in range(per_window):
                    tick = (tick + 1) & 0xff
                    yield dut.i.eq(tick)
                    yield
                # Latch and read back.
                yield dut.latch.eq(1)
                yield
                yield dut.latch.eq(0)
                yield
                seen.append((yield dut.o))
        run_simulation(dut, gen())

        # Each window must report exactly `per_window` ticks.
        self.assertEqual(seen, [per_window]*nwindows)


class TestFreqMeter(unittest.TestCase):
    def test_instantiation(self):
        # Smoke test: the full FreqMeter builds cleanly. End-to-end measurement across the
        # sys/fmeter CDC is covered indirectly via the _Sampler tests above and full-SoC
        # integration tests — migen's sim loop makes it awkward to drive an arbitrary
        # externally-wired clock domain reliably in a unit test.
        dut = FreqMeter(period=100, width=6)
        self.assertEqual(len(dut.value.status), 32)


if __name__ == "__main__":
    unittest.main()
