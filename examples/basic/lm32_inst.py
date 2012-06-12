from migen.fhdl.structure import *
from migen.fhdl import verilog

class LM32:
	def __init__(self):
		self.inst = Instance("lm32_top",
			[("I_ADR_O", BV(32)),
			("I_DAT_O", BV(32)),
			("I_SEL_O", BV(4)),
			("I_CYC_O", BV(1)),
			("I_STB_O", BV(1)),
			("I_WE_O", BV(1)),
			("I_CTI_O", BV(3)),
			("I_LOCK_O", BV(1)),
			("I_BTE_O", BV(1)),
			("D_ADR_O", BV(32)),
			("D_DAT_O", BV(32)),
			("D_SEL_O", BV(4)),
			("D_CYC_O", BV(1)),
			("D_STB_O", BV(1)),
			("D_WE_O", BV(1)),
			("D_CTI_O", BV(3)),
			("D_LOCK_O", BV(1)),
			("D_BTE_O", BV(1))],
			[("interrupt", BV(32)),
			("ext_break", BV(1)),
			("I_DAT_I", BV(32)),
			("I_ACK_I", BV(1)),
			("I_ERR_I", BV(1)),
			("I_RTY_I", BV(1)),
			("D_DAT_I", BV(32)),
			("D_ACK_I", BV(1)),
			("D_ERR_I", BV(1)),
			("D_RTY_I", BV(1))],
			clkport="clk_i",
			rstport="rst_i",
			name="lm32")
	
	def get_fragment(self):
		return Fragment(instances=[self.inst])

cpus = [LM32() for i in range(4)]
frag = Fragment()
for cpu in cpus:
	frag += cpu.get_fragment()
print(verilog.convert(frag, set([cpus[0].inst.ins["interrupt"], cpus[0].inst.outs["I_WE_O"]])))
