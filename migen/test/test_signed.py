import unittest

from migen.fhdl.std import *
from migen.test.support import SimCase, SimBench

class SignedCase(SimCase, unittest.TestCase):
	class TestBench(SimBench):
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
		values = range(-4, 4)
		agen = iter(values)
		bgen = iter(values)
		def cb(tb, s):
			try:
				s.wr(self.tb.a, next(agen))
				s.wr(self.tb.b, next(bgen))
			except StopIteration:
				s.interrupt = True
			a = s.rd(self.tb.a)
			b = s.rd(self.tb.b)
			for asign, bsign, f, r, op in self.tb.vals:
				r, r0 = s.rd(r), f(asign*a, bsign*b)
				self.assertEqual(r, int(r0),
						"got {}, want {}*{} {} {}*{} = {}".format(
							r, asign, a, op, bsign, b, r0))
		self.run_with(cb)
