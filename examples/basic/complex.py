from migen.fhdl.module import Module
from migen.genlib.complex import *
from migen.fhdl import verilog

class Example(Module):
	def __init__(self):
		w = Complex(32, 42)
		A = SignalC(16)
		B = SignalC(16)
		Bw = SignalC(16, variable=True)
		C = SignalC(16)
		D = SignalC(16)
		self.sync += [
			Bw.eq(B*w),
			C.eq(A + Bw),
			D.eq(A - Bw)
		]

print(verilog.convert(Example()))
