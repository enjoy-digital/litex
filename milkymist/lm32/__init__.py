from migen.fhdl.structure import *
from migen.bus import wishbone

class LM32:
	def __init__(self):
		self.ibus = i = wishbone.Interface()
		self.dbus = d = wishbone.Interface()
		self.interrupt = Signal(BV(32))
		self.ext_break = Signal()
		self._inst = Instance("lm32_top",
			[("I_ADR_O", BV(32)),
			("I_DAT_O", i.dat_w),
			("I_SEL_O", i.sel),
			("I_CYC_O", i.cyc),
			("I_STB_O", i.stb),
			("I_WE_O", i.we),
			("I_CTI_O", i.cti),
			("I_LOCK_O", BV(1)),
			("I_BTE_O", i.bte),
			("D_ADR_O", BV(32)),
			("D_DAT_O", d.dat_w),
			("D_SEL_O", d.sel),
			("D_CYC_O", d.cyc),
			("D_STB_O", d.stb),
			("D_WE_O", d.we),
			("D_CTI_O", d.cti),
			("D_LOCK_O", BV(1)),
			("D_BTE_O", d.bte)],
			
			[("interrupt", self.interrupt),
			#("ext_break", self.ext_break),
			("I_DAT_I", i.dat_r),
			("I_ACK_I", i.ack),
			("I_ERR_I", i.err),
			("I_RTY_I", BV(1)),
			("D_DAT_I", d.dat_r),
			("D_ACK_I", d.ack),
			("D_ERR_I", d.err),
			("D_RTY_I", BV(1))],
			
			clkport="clk_i",
			rstport="rst_i")

	def get_fragment(self):
		comb = [
			self._inst.ins["I_RTY_I"].eq(0),
			self._inst.ins["D_RTY_I"].eq(0),
			self.ibus.adr.eq(self._inst.outs["I_ADR_O"][2:]),
			self.dbus.adr.eq(self._inst.outs["D_ADR_O"][2:])
		]
		return Fragment(comb=comb, instances=[self._inst])
