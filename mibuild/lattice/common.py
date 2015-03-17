from migen.fhdl.std import *
from migen.genlib.io import *

class LatticeAsyncResetSynchronizerImpl(Module):
	def __init__(self, cd, async_reset):
		rst1 = Signal()
		self.specials += [
			Instance("FD1S3BX", i_D=0, i_PD=async_reset,
				i_CK=cd.clk, o_Q=rst1),
			Instance("FD1S3BX", i_D=rst1, i_PD=async_reset,
				i_CK=cd.clk, o_Q=cd.rst)
		]

class LatticeAsyncResetSynchronizer:
	@staticmethod
	def lower(dr):
		return LatticeAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

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
	AsyncResetSynchronizer:	LatticeAsyncResetSynchronizer,
	DDROutput:	LatticeDDROutput
}
