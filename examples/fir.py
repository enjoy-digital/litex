# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from math import cos, pi
from scipy import signal

from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.corelogic.misc import optree
from migen.fhdl import autofragment
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

# A synthesizable FIR filter.
class FIR:
	def __init__(self, coef, wsize=16):
		self.coef = coef
		self.wsize = wsize
		self.i = Signal(BV(self.wsize, True))
		self.o = Signal(BV(self.wsize, True))
	
	def get_fragment(self):
		muls = []
		sync = []
		src = self.i
		for c in self.coef:
			sreg = Signal(BV(self.wsize, True))
			sync.append(sreg.eq(src))
			src = sreg
			c_fp = int(c*2**(self.wsize - 1))
			c_e = Constant(c_fp, BV(bits_for(c_fp), True))
			muls.append(c_e*sreg)
		sum_full = Signal(BV(2*self.wsize-1, True))
		sync.append(sum_full.eq(optree("+", muls)))
		comb = [self.o.eq(sum_full[self.wsize-1:])]
		return Fragment(comb, sync)

# A test bench for our FIR filter.
# Generates a sine wave at the input and records the output.
class TB:
	def __init__(self, fir, frequency):
		self.fir = fir
		self.frequency = frequency
		self.inputs = []
		self.outputs = []
	
	def do_simulation(self, s):
		f = 2**(self.fir.wsize - 1)
		v = 0.1*cos(2*pi*self.frequency*s.cycle_counter)
		s.wr(self.fir.i, int(f*v))
		self.inputs.append(v)
		self.outputs.append(s.rd(self.fir.o)/f)
	
	def get_fragment(self):
		return Fragment(sim=[self.do_simulation])

def main():
	# Compute filter coefficients with SciPy.
	coef = signal.remez(80, [0, 0.1, 0.1, 0.5], [1, 0])
	fir = FIR(coef)
	tb = TB(fir, 0.3)
	# Combine the FIR filter with its test bench.
	fragment = autofragment.from_local()
	sim = Simulator(fragment, Runner())
	sim.run(200)
	# Print data from the input and output waveforms.
	# When matplotlib works easily with Python 3, we could
	# display them graphically here.
	print(tb.inputs)
	print(tb.outputs)

main()
