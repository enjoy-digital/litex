import unittest

from migen.fhdl.std import *
from migen.test.support import SimCase, SimBench


class ConstantCase(SimCase, unittest.TestCase):
    class TestBench(SimBench):
        def __init__(self):
            self.sigs = [
                (Signal(3), Constant(0), 0),
                (Signal(3), Constant(5), 5),
                (Signal(3), Constant(1, 2), 1),
                (Signal(3), Constant(-1, 7), 7),
                (Signal(3), Constant(0b10101)[:3], 0b101),
                (Signal(3), Constant(0b10101)[1:4], 0b10),
            ]
            self.comb += [a.eq(b) for a, b, c in self.sigs]

    def test_comparisons(self):
        def cb(tb, tbp):
            for s, l, v in tb.sigs:
                s = tbp.simulator.rd(s)
                self.assertEqual(
                    s, int(v),
                    "got {}, want {} from literal {}".format(
                        s, v, l))
        self.run_with(cb, 1)
