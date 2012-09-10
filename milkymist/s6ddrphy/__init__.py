from migen.fhdl.structure import *
from migen.bus import dfi

class S6DDRPHY:
	def __init__(self, a, ba, d):
		inst_items = [
			Instance.Parameter("NUM_AD", a),
			Instance.Parameter("NUM_BA", ba),
			Instance.Parameter("NUM_D", d),
			Instance.ClockPort("sys_clk")
		]
		for name, width, cl in [
			("clk2x_270", 1, Instance.Input),
			("clk4x_wr", 1, Instance.Input),
			("clk4x_wr_strb", 1, Instance.Input),
			("clk4x_rd", 1, Instance.Input),
			("clk4x_rd_strb", 1, Instance.Input),
			
			("sd_clk_out_p", 1, Instance.Output),
			("sd_clk_out_n", 1, Instance.Output),
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
			s = Signal(BV(width), name=name)
			setattr(self, name, s)
			inst_items.append(cl(name, s))
		
		self.dfi = dfi.Interface(a, ba, d, 2)
		inst_items += [Instance.Input(name, signal) 
			for name, signal in self.dfi.get_standard_names(True, False)]
		inst_items += [Instance.Output(name, signal)
			for name, signal in self.dfi.get_standard_names(False, True)]
		
		self._inst = Instance("s6ddrphy", *inst_items)

	def get_fragment(self):
		return Fragment(instances=[self._inst])
