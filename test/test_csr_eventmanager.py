#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr_eventmanager import (
    EventManager,
    EventSourceLevel,
    EventSourcePulse,
    EventSourceProcess,
)


# EventSourcePulse --------------------------------------------------------------------------------

class TestEventSourcePulse(unittest.TestCase):
    def test_latches_on_pulse(self):
        dut = EventSourcePulse()

        def gen():
            yield dut.trigger.eq(1)
            yield
            yield dut.trigger.eq(0)
            yield
            # pending latches to 1 on the next cycle after trigger rose.
            self.assertEqual((yield dut.pending), 1)
            # status is always 0 for pulse sources.
            self.assertEqual((yield dut.status), 0)
        run_simulation(dut, gen())

    def test_clear_deasserts_pending(self):
        dut = EventSourcePulse()

        def gen():
            yield dut.trigger.eq(1)
            yield
            yield dut.trigger.eq(0)
            yield
            self.assertEqual((yield dut.pending), 1)
            # Now clear: pending drops on the next cycle.
            yield dut.clear.eq(1)
            yield
            yield dut.clear.eq(0)
            yield
            self.assertEqual((yield dut.pending), 0)
        run_simulation(dut, gen())

    def test_trigger_overrides_clear(self):
        # In EventSourcePulse the trigger assignment comes after clear in the sync block, so a
        # simultaneous trigger+clear must leave pending=1.
        dut = EventSourcePulse()

        def gen():
            yield dut.trigger.eq(1)
            yield dut.clear.eq(1)
            yield
            yield dut.trigger.eq(0)
            yield dut.clear.eq(0)
            yield
            self.assertEqual((yield dut.pending), 1)
        run_simulation(dut, gen())


# EventSourceLevel --------------------------------------------------------------------------------

class TestEventSourceLevel(unittest.TestCase):
    def test_pending_mirrors_trigger(self):
        dut = EventSourceLevel()

        def gen():
            yield dut.trigger.eq(0)
            yield
            self.assertEqual((yield dut.pending), 0)
            self.assertEqual((yield dut.status), 0)
            yield dut.trigger.eq(1)
            yield
            self.assertEqual((yield dut.pending), 1)
            self.assertEqual((yield dut.status), 1)
            yield dut.trigger.eq(0)
            yield
            self.assertEqual((yield dut.pending), 0)
        run_simulation(dut, gen())


# EventSourceProcess ------------------------------------------------------------------------------

class TestEventSourceProcess(unittest.TestCase):
    def test_rising_edge(self):
        dut = EventSourceProcess(edge="rising")

        def gen():
            # Start low, pending 0.
            yield dut.trigger.eq(0)
            yield
            yield
            self.assertEqual((yield dut.pending), 0)
            # Rising edge: pending latches.
            yield dut.trigger.eq(1)
            yield
            yield
            self.assertEqual((yield dut.pending), 1)
            # Clear and verify back to 0.
            yield dut.clear.eq(1)
            yield
            yield dut.clear.eq(0)
            yield
            self.assertEqual((yield dut.pending), 0)
            # Holding high does not re-trigger.
            yield
            self.assertEqual((yield dut.pending), 0)
        run_simulation(dut, gen())

    def test_falling_edge(self):
        dut = EventSourceProcess(edge="falling")

        def gen():
            # Bring trigger up; no pending yet.
            yield dut.trigger.eq(1)
            yield
            yield
            self.assertEqual((yield dut.pending), 0)
            # Falling edge → pending.
            yield dut.trigger.eq(0)
            yield
            yield
            self.assertEqual((yield dut.pending), 1)
        run_simulation(dut, gen())

    def test_any_edge(self):
        dut = EventSourceProcess(edge="any")

        def gen():
            yield dut.trigger.eq(0)
            yield
            # Rising edge.
            yield dut.trigger.eq(1)
            yield
            yield
            self.assertEqual((yield dut.pending), 1)
            yield dut.clear.eq(1)
            yield
            yield dut.clear.eq(0)
            yield
            self.assertEqual((yield dut.pending), 0)
            # Falling edge.
            yield dut.trigger.eq(0)
            yield
            yield
            self.assertEqual((yield dut.pending), 1)
        run_simulation(dut, gen())


# EventManager ------------------------------------------------------------------------------------

class _ManagerDUT(Module):
    """Tiny parent with an EventManager + two sources.

    Note: EventManager's CSRStatus/CSRStorage registers are normally finalized by the enclosing
    SoC's CSR bank (it supplies `busword` / `ordering`). In a standalone unit test these
    finalizers can't run, so the aggregated `.status` signals of `pending` / `status` / `enable`
    stay 0 and `ev.irq` can't be exercised here. The individual `fields.<name>` signals ARE
    driven combinationally by EventManager's own comb, so we verify the per-source plumbing via
    those.
    """
    def __init__(self):
        self.ev   = EventManager()
        self.ev.a = EventSourceProcess(edge="rising")
        self.ev.b = EventSourceProcess(edge="rising")
        self.submodules += self.ev


class TestEventManager(unittest.TestCase):
    def test_pending_fields_reflect_sources(self):
        # EventManager drives pending.fields.<name> from the matching source's pending.
        dut = _ManagerDUT()

        def gen():
            yield dut.ev.b.trigger.eq(1)
            yield
            yield dut.ev.b.trigger.eq(0)
            yield
            yield
            self.assertEqual((yield dut.ev.pending.fields.a), 0)
            self.assertEqual((yield dut.ev.pending.fields.b), 1)

            yield dut.ev.a.trigger.eq(1)
            yield
            yield dut.ev.a.trigger.eq(0)
            yield
            yield
            self.assertEqual((yield dut.ev.pending.fields.a), 1)
            self.assertEqual((yield dut.ev.pending.fields.b), 1)
        run_simulation(dut, gen())

    def test_clear_propagates_to_source(self):
        # Writing 1 to pending.fields.<name> via the CSR `re`/`r` path drives source.clear for
        # that source on the next cycle. We emulate the CSR write by forcing `re` and `r`.
        dut = _ManagerDUT()

        def gen():
            yield dut.ev.a.trigger.eq(1)
            yield
            yield dut.ev.a.trigger.eq(0)
            yield
            yield
            self.assertEqual((yield dut.ev.a.pending), 1)

            # Simulate "write-1-to-clear" on the pending.a bit: pending.re pulse while r[0]=1.
            yield dut.ev.pending.r.eq(0b01)
            yield dut.ev.pending.re.eq(1)
            yield
            yield dut.ev.pending.re.eq(0)
            yield dut.ev.pending.r.eq(0)
            yield
            self.assertEqual((yield dut.ev.a.pending), 0)
        run_simulation(dut, gen())


if __name__ == "__main__":
    unittest.main()
