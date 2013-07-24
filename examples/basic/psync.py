from migen.fhdl.std import *
from migen.fhdl.specials import SynthesisDirective
from migen.fhdl import verilog
from migen.genlib.cdc import *

class XilinxMultiRegImpl(MultiRegImpl):
	def __init__(self, *args, **kwargs):
		MultiRegImpl.__init__(self, *args, **kwargs)
		self.specials += set(SynthesisDirective("attribute shreg_extract of {r} is no", r=r)
			for r in self.regs)

class XilinxMultiReg:
	@staticmethod
	def lower(dr):
		return XilinxMultiRegImpl(dr.i, dr.o, dr.odomain, dr.n)

ps = PulseSynchronizer("from", "to")
v = verilog.convert(ps, {ps.i, ps.o}, special_overrides={MultiReg: XilinxMultiReg})
print(v)
