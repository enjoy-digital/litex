# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from math import cos, pi
from scipy import signal
import matplotlib.pyplot as plt

from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.genlib.misc import optree
from migen.fhdl import autofragment
from migen.sim.generic import Simulator, PureSimulable

# A synthesizable FIR filter.
class FIR:
	def __init__(self, coef, wsize=16):
		self.coef = coef
		self.wsize = wsize
		self.i = Signal((self.wsize, True))
		self.o = Signal((self.wsize, True))
	
	def get_fragment(self):
		muls = []
		sync = []
		src = self.i
		for c in self.coef:
			sreg = Signal((self.wsize, True))
			sync.append(sreg.eq(src))
			src = sreg
			c_fp = int(c*2**(self.wsize - 1))
			muls.append(c_fp*sreg)
		sum_full = Signal((2*self.wsize-1, True))
		sync.append(sum_full.eq(optree("+", muls)))
		comb = [self.o.eq(sum_full[self.wsize-1:])]
		return Fragment(comb, sync)

# A test bench for our FIR filter.
# Generates a sine wave at the input and records the output.
class TB(PureSimulable):
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

def main():
	# Compute filter coefficients with SciPy.
	coef = signal.remez(80, [0, 0.1, 0.1, 0.5], [1, 0])
	fir = FIR(coef)
	
	# Simulate for different frequencies and concatenate
	# the results.
	in_signals = []
	out_signals = []
	for frequency in [0.05, 0.07, 0.1, 0.15, 0.2]:
		tb = TB(fir, frequency)
		fragment = autofragment.from_local()
		sim = Simulator(fragment)
		sim.run(100)
		del sim
		in_signals += tb.inputs
		out_signals += tb.outputs
	
	# Plot data from the input and output waveforms.
	plt.plot(in_signals)
	plt.plot(out_signals)
	plt.show()
	
	# Print the Verilog source for the filter.
	print(verilog.convert(fir.get_fragment(),
		ios={fir.i, fir.o}))

main()
