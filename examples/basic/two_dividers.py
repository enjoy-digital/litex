from migen.fhdl.std import *
from migen.fhdl import verilog
from migen.genlib import divider

class Example(Module):
	def __init__(self):
		d1 = divider.Divider(16)
		d2 = divider.Divider(16)
		self.submodules += d1, d2
		self.ios = {
			d1.ready_o, d1.quotient_o, d1.remainder_o, d1.start_i, d1.dividend_i, d1.divisor_i,
			d2.ready_o, d2.quotient_o, d2.remainder_o, d2.start_i, d2.dividend_i, d2.divisor_i}

example = Example()
print(verilog.convert(example, example.ios))
