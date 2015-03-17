from migen.fhdl.std import *
from migen.genlib.io import *

class LatticeDDROutputImpl(Module):
	def __init__(self, i1, i2, o, clk):
		self.specials += Instance("ODDRA",
				i_CLK=clk, i_RST=0,
				i_DA=i1, i_DB=i2, o_Q=o,
		)

class LatticeDDROutput:
	@staticmethod
	def lower(dr):
		return LatticeDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

lattice_special_overrides = {
	DDROutput:	LatticeDDROutput
}
