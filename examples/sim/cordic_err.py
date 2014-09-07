import random

import numpy as np
import matplotlib.pyplot as plt

from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.genlib.cordic import Cordic
from migen.sim.generic import run_simulation

class TestBench(Module):
	def __init__(self, n=None, xmax=.98, i=None, **kwargs):
		self.submodules.cordic = Cordic(**kwargs)
		if n is None:
			n = 1<<flen(self.cordic.xi)
		self.c = c = 2**(flen(self.cordic.xi) - 1)
		self.cz = cz = 2**(flen(self.cordic.zi) - 1)
		x = int(xmax*c/self.cordic.gain)
		if i is None:
			i = [(x, 0, int(cz*(2.*ii/n - 1))) for ii in range(n)]
		self.i = i
		random.shuffle(self.i)
		self.ii = iter(self.i)
		self.o = []

	def do_simulation(self, selfp):
		if selfp.cordic.new_out:
			self.o.append((selfp.cordic.xo, selfp.cordic.yo, selfp.cordic.zo))
		if selfp.cordic.new_in:
			try:
				selfp.cordic.xi, selfp.cordic.yi, selfp.cordic.zi = next(self.ii)
			except StopIteration:
				raise StopSimulation

	def run_io(self):
		run_simulation(self)
		del self.o[0]
		if self.i[0] != (0, 0, 0):
			assert self.o[0] != (0, 0, 0)
		#if self.i[-1] != self.i[-2]:
		#	assert self.o[-1] != self.o[-2], self.o[-2:]

def rms_err(width, guard=None, stages=None, n=None):
	tb = TestBench(width=width, guard=guard, stages=stages,
			n=n, eval_mode="combinatorial")
	tb.run_io()
	c = 2**(flen(tb.cordic.xi) - 1)
	cz = 2**(flen(tb.cordic.zi) - 1)
	g = tb.cordic.gain
	xi, yi, zi = np.array(tb.i).T/c
	zi *= c/cz*tb.cordic.zmax
	xo1, yo1, zo1 = np.array(tb.o).T
	xo = np.floor(c*g*(np.cos(zi)*xi - np.sin(zi)*yi))
	yo = np.floor(c*g*(np.sin(zi)*xi + np.cos(zi)*yi))
	dx = xo1 - xo
	dy = yo1 - yo
	mm = np.fabs([dx, dy]).max()
	rms = np.sqrt(dx**2 + dy**2).sum()/len(xo)
	return rms, mm

def rms_err_map():
	widths, stages = np.mgrid[8:33:1, 8:37:1]
	errf = np.vectorize(lambda w, s: rms_err(int(w), None, int(s), n=333))
	err = errf(widths, stages)
	print(err)
	lev = np.arange(10)
	fig, ax = plt.subplots()
	c1 = ax.contour(widths, stages, err[0], lev/10, cmap=plt.cm.Greys_r)
	c2 = ax.contour(widths, stages, err[1], lev, cmap=plt.cm.Reds_r)
	ax.plot(widths[:, 0], stages[0, np.argmin(err[0], 1)], "ko")
	ax.plot(widths[:, 0], stages[0, np.argmin(err[1], 1)], "ro")
	print(widths[:, 0], stages[0, np.argmin(err[0], 1)],
			stages[0, np.argmin(err[1], 1)])
	ax.set_xlabel("width")
	ax.set_ylabel("stages")
	ax.grid("on")
	fig.colorbar(c1)
	fig.colorbar(c2)
	fig.savefig("cordic_rms.pdf")

def plot_function(**kwargs):
	tb = TestBench(eval_mode="combinatorial", **kwargs)
	tb.run_io()
	c = 2**(flen(tb.cordic.xi) - 1)
	cz = 2**(flen(tb.cordic.zi) - 1)
	g = tb.cordic.gain
	xi, yi, zi = np.array(tb.i).T
	xo, yo, zo = np.array(tb.o).T
	fig, ax = plt.subplots()
	#ax.plot(zi, xo-np.around(xi[0]*g*np.cos(zi/cz*np.pi)), "k-")
	ax.plot(zi, xo, "r,")
	ax.plot(zi, yo, "g,")
	ax.plot(zi, zo, "b,")


if __name__ == "__main__":
	c = Cordic(width=16, guard=None, eval_mode="combinatorial")
	print(verilog.convert(c, ios={c.xi, c.yi, c.zi, c.xo, c.yo, c.zo,
		c.new_in, c.new_out}))
	#print(rms_err(8))
	#rms_err_map()
	#plot_function(func_mode="hyperbolic", xmax=.3, width=16, n=333)
	#plot_function(func_mode="circular", width=16, n=333)
	#plot_function(func_mode="hyperbolic", cordic_mode="vector",
	#        xmax=.3, width=16, n=333)
	plot_function(func_mode="circular",
			width=16, stages=15, guard=0,
			n=1000, xmax=.98)
	plt.show()
