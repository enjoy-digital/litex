from migen.fhdl.structure import *
from migen.fhdl.specials import SynthesisDirective
from migen.fhdl import verilog
from migen.genlib.cdc import *

class XilinxMultiRegImpl(MultiRegImpl):
	def get_fragment(self):
		disable_srl = set(SynthesisDirective("attribute shreg_extract of {r} is no", r=r)
			for r in self.regs)
		return MultiRegImpl.get_fragment(self) + Fragment(specials=disable_srl)

class XilinxMultiReg:
	@staticmethod
	def lower(dr):
		return XilinxMultiRegImpl(dr.i, dr.o, dr.odomain, dr.n)

ps = PulseSynchronizer("from", "to")
v = verilog.convert(ps, {ps.i, ps.o}, special_overrides={MultiReg: XilinxMultiReg})
print(v)
