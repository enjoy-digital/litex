import unittest
from random import randrange, random
from math import *

from migen.fhdl.std import *
from migen.genlib.cordic import *

from migen.test.support import SimCase, SimBench


class CordicCase(SimCase, unittest.TestCase):
	class TestBench(SimBench):
		def __init__(self, **kwargs):
			k = dict(width=8, guard=None, stages=None,
				eval_mode="combinatorial", cordic_mode="rotate",
				func_mode="circular")
			k.update(kwargs)
			self.submodules.dut = Cordic(**k)

	def _run_io(self, n, gen, proc, delta=1, deltaz=1):
		c = 2**(flen(self.tb.dut.xi) - 1)
		g = self.tb.dut.gain
		zm = self.tb.dut.zmax
		pipe = {}
		genn = [gen() for i in range(n)]
		def cb(tb, s):
			if s.rd(tb.dut.new_in):
				if genn:
					xi, yi, zi = genn.pop(0)
				else:
					s.interrupt = True
					return
				xi = floor(xi*c/g)
				yi = floor(yi*c/g)
				zi = floor(zi*c/zm)
				s.wr(tb.dut.xi, xi)
				s.wr(tb.dut.yi, yi)
				s.wr(tb.dut.zi, zi)
				pipe[s.cycle_counter] = xi, yi, zi
			if s.rd(tb.dut.new_out):
				t = s.cycle_counter - tb.dut.latency - 1
				if t < 1:
					return
				xi, yi, zi = pipe.pop(t)
				xo, yo, zo = proc(xi/c, yi/c, zi/c*zm)
				xo = floor(xo*c*g)
				yo = floor(yo*c*g)
				zo = floor(zo*c/zm)
				xo1 = s.rd(tb.dut.xo)
				yo1 = s.rd(tb.dut.yo)
				zo1 = s.rd(tb.dut.zo)
				print((xi, yi, zi), (xo, yo, zo), (xo1, yo1, zo1))
				self.assertAlmostEqual(xo, xo1, delta=delta)
				self.assertAlmostEqual(yo, yo1, delta=delta)
				self.assertAlmostEqual(abs(zo - zo1) % (2*c), 0, delta=deltaz)
		self.run_with(cb)

	def test_rot_circ(self):
		def gen():
			ti = 2*pi*random()
			r = random()*.98
			return r*cos(ti), r*sin(ti), (2*random() - 1)*pi
		def proc(xi, yi, zi):
			xo = cos(zi)*xi - sin(zi)*yi
			yo = sin(zi)*xi + cos(zi)*yi
			return xo, yo, 0
		self._run_io(50, gen, proc, delta=2)

	def test_rot_circ_16(self):
		self.setUp(width=16)
		self.test_rot_circ()

	def test_rot_circ_pipe(self):
		self.setUp(eval_mode="pipelined")
		self.test_rot_circ()

	def test_rot_circ_iter(self):
		self.setUp(eval_mode="iterative")
		self.test_rot_circ()

	def _test_vec_circ(self):
		def gen():
			ti = pi*(2*random() - 1)
			r = .98 #*random()
			return r*cos(ti), r*sin(ti), 0 #pi*(2*random() - 1)
		def proc(xi, yi, zi):
			return sqrt(xi**2 + yi**2), 0, zi + atan2(yi, xi)
		self._run_io(50, gen, proc)

	def test_vec_circ(self):
		self.setUp(cordic_mode="vector")
		self._test_vec_circ()

	def test_vec_circ_16(self):
		self.setUp(width=16, cordic_mode="vector")
		self._test_vec_circ()

	def _test_rot_hyp(self):
		def gen():
			return .6, 0, 2.1*(random() - .5)
		def proc(xi, yi, zi):
			xo = cosh(zi)*xi - sinh(zi)*yi
			yo = sinh(zi)*xi + cosh(zi)*yi
			return xo, yo, 0
		self._run_io(50, gen, proc, delta=2)

	def test_rot_hyp(self):
		self.setUp(func_mode="hyperbolic")
		self._test_rot_hyp()

	def test_rot_hyp_16(self):
		self.setUp(func_mode="hyperbolic", width=16)
		self._test_rot_hyp()

	def test_rot_hyp_iter(self):
		self.setUp(cordic_mode="rotate", func_mode="hyperbolic",
				eval_mode="iterative")
		self._test_rot_hyp()

	def _test_vec_hyp(self):
		def gen():
			xi = random()*.6 + .2
			yi = random()*xi*.8
			return xi, yi, 0
		def proc(xi, yi, zi):
			return sqrt(xi**2 - yi**2), 0, atanh(yi/xi)
		self._run_io(50, gen, proc)

	def test_vec_hyp(self):
		self.setUp(cordic_mode="vector", func_mode="hyperbolic")
		self._test_vec_hyp()

	def _test_rot_lin(self):
		def gen():
			xi = 2*random() - 1
			if abs(xi) < .01:
				xi = .01
			yi = (2*random() - 1)*.5
			zi = (2*random() - 1)*.5
			return xi, yi, zi
		def proc(xi, yi, zi):
			return xi, yi + xi*zi, 0
		self._run_io(50, gen, proc)

	def test_rot_lin(self):
		self.setUp(func_mode="linear")
		self._test_rot_lin()

	def _test_vec_lin(self):
		def gen():
			yi = random()*.95 + .05
			if random() > 0:
				yi *= -1
			xi = abs(yi) + random()*(1 - abs(yi))
			zi = 2*random() - 1
			return xi, yi, zi
		def proc(xi, yi, zi):
			return xi, 0, zi + yi/xi
		self._run_io(50, gen, proc, deltaz=2, delta=2)

	def test_vec_lin(self):
		self.setUp(func_mode="linear", cordic_mode="vector", width=8)
		self._test_vec_lin()
