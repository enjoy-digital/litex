import unittest

from migen import *
from migen.test.support import SimCase


class SignedCase(SimCase, unittest.TestCase):
    class TestBench(Module):
        def __init__(self):
            self.a = Signal((3, True))
            self.b = Signal((4, True))
            comps = [
                lambda p, q: p > q,
                lambda p, q: p >= q,
                lambda p, q: p < q,
                lambda p, q: p <= q,
                lambda p, q: p == q,
                lambda p, q: p != q,
            ]
            self.vals = []
            for asign in 1, -1:
                for bsign in 1, -1:
                    for f in comps:
                        r = Signal()
                        r0 = f(asign*self.a, bsign*self.b)
                        self.comb += r.eq(r0)
                        self.vals.append((asign, bsign, f, r, r0.op))

    def test_comparisons(self):
        def gen():
            for i in range(-4, 4):
                yield self.tb.a.eq(i)
                yield self.tb.b.eq(i)
                a = yield self.tb.a
                b = yield self.tb.b
                for asign, bsign, f, r, op in self.tb.vals:
                    r, r0 = (yield r), f(asign*a, bsign*b)
                    self.assertEqual(r, int(r0),
                            "got {}, want {}*{} {} {}*{} = {}".format(
                                r, asign, a, op, bsign, b, r0))
                yield
        self.run_with(gen())
