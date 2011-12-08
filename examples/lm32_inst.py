from migen.fhdl import structure as f
from migen.fhdl import verilog

class LM32:
	def __init__(self):
		self.inst = f.Instance("lm32_top",
			[("I_ADR_O", f.BV(32)),
			("I_DAT_O", f.BV(32)),
			("I_SEL_O", f.BV(4)),
			("I_CYC_O", f.BV(1)),
			("I_STB_O", f.BV(1)),
			("I_WE_O", f.BV(1)),
			("I_CTI_O", f.BV(3)),
			("I_LOCK_O", f.BV(1)),
			("I_BTE_O", f.BV(1)),
			("D_ADR_O", f.BV(32)),
			("D_DAT_O", f.BV(32)),
			("D_SEL_O", f.BV(4)),
			("D_CYC_O", f.BV(1)),
			("D_STB_O", f.BV(1)),
			("D_WE_O", f.BV(1)),
			("D_CTI_O", f.BV(3)),
			("D_LOCK_O", f.BV(1)),
			("D_BTE_O", f.BV(1))],
			[("interrupt", f.BV(32)),
			("ext_break", f.BV(1)),
			("I_DAT_I", f.BV(32)),
			("I_ACK_I", f.BV(1)),
			("I_ERR_I", f.BV(1)),
			("I_RTY_I", f.BV(1)),
			("D_DAT_I", f.BV(32)),
			("D_ACK_I", f.BV(1)),
			("D_ERR_I", f.BV(1)),
			("D_RTY_I", f.BV(1))],
			[],
			"clk_i",
			"rst_i",
			"lm32")
	
	def GetFragment(self):
		return f.Fragment(instances=[self.inst])

cpus = [LM32() for i in range(4)]
frag = f.Fragment()
for cpu in cpus:
	frag += cpu.GetFragment()
print(verilog.Convert(frag, set([cpus[0].inst.ins["interrupt"], cpus[0].inst.outs["I_WE_O"]])))