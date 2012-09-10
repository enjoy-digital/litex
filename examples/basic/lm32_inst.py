from migen.fhdl.structure import *
from migen.fhdl import verilog

class LM32:
	def __init__(self):
		self.inst = Instance("lm32_top",
			Instance.ClockPort("clk_i"),
			Instance.ResetPort("rst_i"),
		
			Instance.Input("interrupt", BV(32)),
			Instance.Input("ext_break", BV(1)),
		
			Instance.Output("I_ADR_O", BV(32)),
			Instance.Output("I_DAT_O", BV(32)),
			Instance.Output("I_SEL_O", BV(4)),
			Instance.Output("I_CYC_O", BV(1)),
			Instance.Output("I_STB_O", BV(1)),
			Instance.Output("I_WE_O", BV(1)),
			Instance.Output("I_CTI_O", BV(3)),
			Instance.Output("I_LOCK_O", BV(1)),
			Instance.Output("I_BTE_O", BV(1)),
			Instance.Input("I_DAT_I", BV(32)),
			Instance.Input("I_ACK_I", BV(1)),
			Instance.Input("I_ERR_I", BV(1)),
			Instance.Input("I_RTY_I", BV(1)),
			
			Instance.Output("D_ADR_O", BV(32)),
			Instance.Output("D_DAT_O", BV(32)),
			Instance.Output("D_SEL_O", BV(4)),
			Instance.Output("D_CYC_O", BV(1)),
			Instance.Output("D_STB_O", BV(1)),
			Instance.Output("D_WE_O", BV(1)),
			Instance.Output("D_CTI_O", BV(3)),
			Instance.Output("D_LOCK_O", BV(1)),
			Instance.Output("D_BTE_O", BV(1)),
			Instance.Input("D_DAT_I", BV(32)),
			Instance.Input("D_ACK_I", BV(1)),
			Instance.Input("D_ERR_I", BV(1)),
			Instance.Input("D_RTY_I", BV(1)),
			
			name="lm32")
	
	def get_fragment(self):
		return Fragment(instances=[self.inst])

cpus = [LM32() for i in range(4)]
frag = Fragment()
for cpu in cpus:
	frag += cpu.get_fragment()
print(verilog.convert(frag, set([cpus[0].inst.get_io("interrupt"), cpus[0].inst.get_io("I_WE_O")])))
