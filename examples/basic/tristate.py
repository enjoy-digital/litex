from migen.fhdl.structure import *
from migen.fhdl.specials import Tristate
from migen.fhdl.module import Module
from migen.fhdl import verilog

class Example(Module):
	def __init__(self, n=6):
		self.pad = Signal(n)
		self.o = Signal(n)
		self.oe = Signal()
		self.i = Signal(n)

		self.specials += Tristate(self.pad, self.o, self.oe, self.i)

e = Example()
print(verilog.convert(e, ios={e.pad, e.o, e.oe, e.i}))
