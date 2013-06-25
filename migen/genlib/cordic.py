from math import atan, atanh, log, sqrt, pi

from migen.fhdl.std import *


class TwoQuadrantCordic(Module):
	"""
	http://eprints.soton.ac.uk/267873/1/tcas1_cordic_review.pdf
	"""
	def __init__(self, width=16, stages=None, guard=0,
			eval_mode="iterative", cordic_mode="rotate",
			func_mode="circular"):
		# validate paramters
		assert eval_mode in ("combinatorial", "pipelined", "iterative")
		assert cordic_mode in ("rotate", "vector")
		self.cordic_mode = cordic_mode
		assert func_mode in ("circular", "linear", "hyperbolic")
		self.func_mode = func_mode
		if guard is None:
			# guard bits to guarantee "width" accuracy
			guard = int(log(width)/log(2))
		if stages is None:
			stages = width + guard

		# calculate the constants
		if func_mode == "circular":
			s = range(stages)
			a = [atan(2**-i) for i in s]
			g = [sqrt(1 + 2**(-2*i)) for i in s]
			zmax = pi/2
		elif func_mode == "linear":
			s = range(stages)
			a = [2**-i for i in s]
			g = [1 for i in s]
			zmax = 2.
		elif func_mode == "hyperbolic":
			s = list(range(1, stages+1))
			# need to repeat these stages:
			j = 4
			while j < stages+1:
				s.append(j)
				j = 3*j + 1
			s.sort()
			stages = len(s)
			a = [atanh(2**-i) for i in s]
			g = [sqrt(1 - 2**(-2*i)) for i in s]
			zmax = 1.

		a = [Signal((width+guard, True), "{}{}".format("a", i),
			reset=int(round(ai*2**(width + guard - 1)/zmax)))
			for i, ai in enumerate(a)]
		self.zmax = zmax #/2**(width - 1)
		self.gain = 1.
		for gi in g:
			self.gain *= gi

		exec_target, num_reg, self.latency, self.interval = {
			"combinatorial": (self.comb, stages + 1, 0,          1),
			"pipelined":     (self.sync, stages + 1, stages,     1),
			"iterative":     (self.sync, 3,          stages + 1, stages + 1),
			}[eval_mode]

		# i/o and inter-stage signals
		self.fresh = Signal()
		self.xi, self.yi, self.zi, self.xo, self.yo, self.zo = (
				Signal((width, True), l + io) for io in "io" for l in "xyz")
		x, y, z = ([Signal((width + guard, True), "{}{}".format(l, i))
			for i in range(num_reg)] for l in "xyz")

		self.comb += [
			x[0].eq(self.xi<<guard),
			y[0].eq(self.yi<<guard),
			z[0].eq(self.zi<<guard),
			self.xo.eq(x[-1]>>guard),
			self.yo.eq(y[-1]>>guard),
			self.zo.eq(z[-1]>>guard),
			]

		if eval_mode in ("combinatorial", "pipelined"):
			self.comb += self.fresh.eq(1)
			for i in range(stages):
				exec_target += self.stage(x[i], y[i], z[i],
						x[i + 1], y[i + 1], z[i + 1], i, a[i])
		elif eval_mode == "iterative":
			# we afford one additional iteration for register in/out
			# shifting, trades muxes for registers
			i = Signal(max=stages + 1)
			ai = Signal((width+guard, True))
			self.comb += ai.eq(Array(a)[i])
			exec_target += [
					i.eq(i + 1),
					If(i == stages,
						i.eq(0),
						self.fresh.eq(1),
						Cat(x[1], y[1], z[1]).eq(Cat(x[0], y[0], z[0])),
						Cat(x[2], y[2], z[2]).eq(Cat(x[1], y[1], z[1])),
					).Else(
						self.fresh.eq(0),
						# in-place stages
						self.stage(x[1], y[1], z[1], x[1], y[1], z[1], i, ai),
					)]

	def stage(self, xi, yi, zi, xo, yo, zo, i, a):
		"""
		x_{i+1} = x_{i} - m*d_i*y_i*r**(-s_{m,i})
		y_{i+1} = d_i*x_i*r**(-s_{m,i}) + y_i
		z_{i+1} = z_i - d_i*a_{m,i}

		d_i: clockwise or counterclockwise
		r: radix of the number system
		m: 1: circular, 0: linear, -1: hyperbolic
		s_{m,i}: non decreasing integer shift sequence
		a_{m,i}: elemetary rotation angle
		"""
		dx, dy, dz = xi>>i, yi>>i, a
		# FIXME need 1'sd0 here, "Signal((n, True)) >= 0" is always true
		# as 1'd0 makes the comparison unsigned
		direction = {"rotate": zi[-1], "vector": ~yi[-1]}[self.cordic_mode]
		dy = {"circular": dy, "linear": 0, "hyperbolic": -dy}[self.func_mode]
		ret = If(direction,
					xo.eq(xi + dy),
					yo.eq(yi - dx),
					zo.eq(zi + dz),
				).Else(
					xo.eq(xi - dy),
					yo.eq(yi + dx),
					zo.eq(zi - dz),
				)
		return ret



class Cordic(TwoQuadrantCordic):
	def __init__(self, **kwargs):
		TwoQuadrantCordic.__init__(self, **kwargs)
		if not (self.func_mode, self.cordic_mode) == ("circular", "rotate"):
			return # no need to remap quadrants
		cxi, cyi, czi, cxo, cyo, czo = (self.xi, self.yi, self.zi,
				self.xo, self.yo, self.zo)
		width = flen(self.xi)
		for l in "xyz":
			for d in "io":
				setattr(self, l+d, Signal((width, True), l+d))
		qin = Signal()
		qout = Signal()
		if self.latency == 0:
			self.comb += qout.eq(qin)
		elif self.latency == 1:
			self.sync += qout.eq(qin)
		else:
			sr = Signal(self.latency-1)
			self.sync += Cat(sr, qout).eq(Cat(qin, sr))
		pi2 = (1<<(width-2))-1
		self.zmax *= 2
		self.comb += [
				# zi, zo are scaled to cover the range, this also takes
				# care of mapping the zi quadrants
				Cat(cxi, cyi, czi).eq(Cat(self.xi, self.yi, self.zi<<1)),
				Cat(self.xo, self.yo, self.zo).eq(Cat(cxo, cyo, czo>>1)),
				# shift in the (2,3)-quadrant flag
				qin.eq((-self.zi < -pi2) | (self.zi+1 < -pi2)),
				# need to remap xo/yo quadrants (2,3) -> (4,1)
				If(qout,
					self.xo.eq(-cxo),
					self.yo.eq(-cyo),
				)]


class TB(Module):
	def __init__(self, n, **kwargs):
		self.submodules.cordic = Cordic(**kwargs)
		self.xi = [.9/self.cordic.gain] * n
		self.yi = [0] * n
		self.zi = [2*i/n-1 for i in range(n)]
		self.xo = []
		self.yo = []
		self.zo = []

	def do_simulation(self, s):
		c = 2**(flen(self.cordic.xi)-1)
		if s.rd(self.cordic.fresh):
			self.xo.append(s.rd(self.cordic.xo))
			self.yo.append(s.rd(self.cordic.yo))
			self.zo.append(s.rd(self.cordic.zo))
			if not self.xi:
				s.interrupt = True
				return
			for r, v in zip((self.cordic.xi, self.cordic.yi, self.cordic.zi),
					(self.xi, self.yi, self.zi)):
				s.wr(r, int(v.pop(0)*c))


def main():
	from migen.fhdl import verilog
	from migen.sim.generic import Simulator, TopLevel
	from matplotlib import pyplot as plt
	import numpy as np

	c = Cordic(width=16, eval_mode="iterative",
		cordic_mode="rotate", func_mode="circular")
	print(verilog.convert(c, ios={c.xi, c.yi, c.zi, c.xo,
		c.yo, c.zo}))

	n = 200
	tb = TB(n, width=8, guard=3, eval_mode="pipelined",
			cordic_mode="rotate", func_mode="circular")
	sim = Simulator(tb, TopLevel("cordic.vcd"))
	sim.run(n*16+20)
	plt.plot(tb.xo)
	plt.plot(tb.yo)
	plt.plot(tb.zo)
	plt.show()


def rms_err(width, stages, n):
	from migen.sim.generic import Simulator
	import numpy as np
	import matplotlib.pyplot as plt

	tb = TB(width=int(width), stages=int(stages), n=n,
			eval_mode="combinatorial")
	sim = Simulator(tb)
	sim.run(n+100)
	z = tb.cordic.zmax*(np.arange(n)/n*2-1)
	x = np.cos(z)*.9
	y = np.sin(z)*.9
	dx = tb.xo[1:]-x*2**(width-1)
	dy = tb.yo[1:]-y*2**(width-1)
	return ((dx**2+dy**2)**.5).sum()/n


def test_err():
	from matplotlib import pyplot as plt
	import numpy as np

	widths, stages = np.mgrid[4:33:1, 4:33:1]
	err = np.vectorize(lambda w, s: rms_err(w, s, 173))(widths, stages)
	err = -np.log2(err)/widths
	print(err)
	plt.contour(widths, stages, err, 50, cmap=plt.cm.Greys)
	plt.plot(widths[:, 0], stages[0, np.argmax(err, 1)], "bx-")
	print(widths[:, 0], stages[0, np.argmax(err, 1)])
	plt.colorbar()
	plt.grid("on")
	plt.show()


if __name__ == "__main__":
	main()
	#rms_err(16, 16, 345)
	#test_err()
