from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module
from migen.bus import dfi

class S6DDRPHY(Module):
	def __init__(self, a, ba, d):
		inst_items = [
			Instance.Parameter("NUM_AD", a),
			Instance.Parameter("NUM_BA", ba),
			Instance.Parameter("NUM_D", d),
			Instance.Input("sys_clk", ClockSignal()),
			Instance.Input("clk2x_270", ClockSignal("sys2x_270")),
			Instance.Input("clk4x_wr", ClockSignal("sys4x_wr")),
			Instance.Input("clk4x_rd", ClockSignal("sys4x_rd"))
		]
		for name, width, cl in [
			("clk4x_wr_strb", 1, Instance.Input),
			("clk4x_rd_strb", 1, Instance.Input),
			
			("sd_a", a, Instance.Output),
			("sd_ba", ba, Instance.Output),
			("sd_cs_n", 1, Instance.Output),
			("sd_cke", 1, Instance.Output),
			("sd_ras_n", 1, Instance.Output),
			("sd_cas_n", 1, Instance.Output),
			("sd_we_n", 1, Instance.Output),
			("sd_dq", d//2, Instance.InOut),
			("sd_dm", d//16, Instance.Output),
			("sd_dqs", d//16, Instance.InOut)
			
		]:
			s = Signal(width, name=name)
			setattr(self, name, s)
			inst_items.append(cl(name, s))
		
		self.dfi = dfi.Interface(a, ba, d, 2)
		inst_items += [Instance.Input(name, signal) 
			for name, signal in self.dfi.get_standard_names(True, False)]
		inst_items += [Instance.Output(name, signal)
			for name, signal in self.dfi.get_standard_names(False, True)]
		
		self.specials += Instance("s6ddrphy", *inst_items)
