import unittest

from migen import *
from migen.genlib.fifo import SyncFIFO

from migen.test.support import SimCase, SimBench


class SyncFIFOCase(SimCase, unittest.TestCase):
    class TestBench(SimBench):
        def __init__(self):
            self.submodules.dut = SyncFIFO([("a", 32), ("b", 32)], 2)

            self.sync += [
                If(self.dut.we & self.dut.writable,
                    self.dut.din.a.eq(self.dut.din.a + 1),
                    self.dut.din.b.eq(self.dut.din.b + 2)
                )
            ]

    def test_sizes(self):
        self.assertEqual(flen(self.tb.dut.din_bits), 64)
        self.assertEqual(flen(self.tb.dut.dout_bits), 64)

    def test_run_sequence(self):
        seq = list(range(20))
        def cb(tb, tbp):
            # fire re and we at "random"
            tbp.dut.we = tbp.simulator.cycle_counter % 2 == 0
            tbp.dut.re = tbp.simulator.cycle_counter % 3 == 0
            # the output if valid must be correct
            if tbp.dut.readable and tbp.dut.re:
                try:
                    i = seq.pop(0)
                except IndexError:
                    raise StopSimulation
                self.assertEqual(tbp.dut.dout.a, i)
                self.assertEqual(tbp.dut.dout.b, i*2)
        self.run_with(cb)

    def test_replace(self):
        seq = [x for x in range(20) if x % 5]
        def cb(tb, tbp):
            tbp.dut.we = tbp.simulator.cycle_counter % 2 == 0
            tbp.dut.re = tbp.simulator.cycle_counter % 3 == 0
            tbp.dut.replace = tbp.dut.din.a % 5 == 1
            if tbp.dut.readable and tbp.dut.re:
                try:
                    i = seq.pop(0)
                except IndexError:
                    raise StopSimulation
                self.assertEqual(tbp.dut.dout.a, i)
                self.assertEqual(tbp.dut.dout.b, i*2)
        self.run_with(cb)
