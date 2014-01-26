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
		def cb(tb, tbp):
			try:
				tbp.a = next(agen)
				tbp.b = next(bgen)
			except StopIteration:
				raise StopSimulation
			a = tbp.a
			b = tbp.b
			for asign, bsign, f, r, op in self.tb.vals:
				r, r0 = tbp.simulator.rd(r), f(asign*a, bsign*b)
				self.assertEqual(r, int(r0),
						"got {}, want {}*{} {} {}*{} = {}".format(
							r, asign, a, op, bsign, b, r0))
		self.run_with(cb)
