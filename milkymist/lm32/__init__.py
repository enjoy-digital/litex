from migen.fhdl.structure import *
from migen.bus import wishbone

class LM32:
	def __init__(self):
		self.ibus = i = wishbone.Interface()
		self.dbus = d = wishbone.Interface()
		self.interrupt = Signal(32)
		self.ext_break = Signal()
		self._i_adr_o = Signal(32)
		self._d_adr_o = Signal(32)
		self._inst = Instance("lm32_top",
			Instance.ClockPort("clk_i"),
			Instance.ResetPort("rst_i"),
			
			Instance.Input("interrupt", self.interrupt),
			#Instance.Input("ext_break", self.ext_break),
		
			Instance.Output("I_ADR_O", self._i_adr_o),
			Instance.Output("I_DAT_O", i.dat_w),
			Instance.Output("I_SEL_O", i.sel),
			Instance.Output("I_CYC_O", i.cyc),
			Instance.Output("I_STB_O", i.stb),
			Instance.Output("I_WE_O", i.we),
			Instance.Output("I_CTI_O", i.cti),
			Instance.Output("I_LOCK_O"),
			Instance.Output("I_BTE_O", i.bte),
			Instance.Input("I_DAT_I", i.dat_r),
			Instance.Input("I_ACK_I", i.ack),
			Instance.Input("I_ERR_I", i.err),
			Instance.Input("I_RTY_I", 0),
			
			Instance.Output("D_ADR_O", self._d_adr_o),
			Instance.Output("D_DAT_O", d.dat_w),
			Instance.Output("D_SEL_O", d.sel),
			Instance.Output("D_CYC_O", d.cyc),
			Instance.Output("D_STB_O", d.stb),
			Instance.Output("D_WE_O", d.we),
			Instance.Output("D_CTI_O", d.cti),
			Instance.Output("D_LOCK_O"),
			Instance.Output("D_BTE_O", d.bte),
			Instance.Input("D_DAT_I", d.dat_r),
			Instance.Input("D_ACK_I", d.ack),
			Instance.Input("D_ERR_I", d.err),
			Instance.Input("D_RTY_I", 0))

	def get_fragment(self):
		comb = [
			self.ibus.adr.eq(self._i_adr_o[2:]),
			self.dbus.adr.eq(self._d_adr_o[2:])
		]
		return Fragment(comb=comb, instances=[self._inst])
