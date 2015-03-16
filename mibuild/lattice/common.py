from migen.fhdl.std import *
from migen.genlib.io import *

class LatticeDifferentialOutput:
	@staticmethod
	def lower(dr):
		return LatticeDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

class LatticeDDROutputImpl(Module):
	def __init__(self, i1, i2, o, clk):
		self.specials += Instance("ODDRA",
				i_CLK=clk, i_RST=0,
				i_DA=i1, i_DB=i2, o_Q=o,
		)

lattice_special_overrides = {
	DDROutput:	LatticeDDROutput
}
