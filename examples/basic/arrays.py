from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.fhdl import verilog

class Example(Module):
	def __init__(self):
		dx = 5
		dy = 5

		x = Signal(max=dx)
		y = Signal(max=dy)
		out = Signal()

		my_2d_array = Array(Array(Signal() for a in range(dx)) for b in range(dy))
		self.comb += out.eq(my_2d_array[x][y])

		we = Signal()
		inp = Signal()
		self.sync += If(we,
				my_2d_array[x][y].eq(inp)
			)

print(verilog.convert(Example()))
