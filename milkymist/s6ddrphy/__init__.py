from migen.fhdl.structure import *
from migen.bus import dfi

class S6DDRPHY:
	def __init__(self, a, ba, d):
		ins = []
		outs = []
		inouts = []
		
		for name, width, l in [
			("clk2x_270", 1, ins),
			("clk4x_wr", 1, ins),
			("clk4x_wr_strb", 1, ins),
			("clk4x_rd", 1, ins),
			("clk4x_rd_strb", 1, ins),
			
			("sd_clk_out_p", 1, outs),
			("sd_clk_out_n", 1, outs),
			("sd_a", a, outs),
			("sd_ba", ba, outs),
			("sd_cs_n", 1, outs),
			("sd_cke", 1, outs),
			("sd_ras_n", 1, outs),
			("sd_cas_n", 1, outs),
			("sd_we_n", 1, outs),
			("sd_dq", d//2, inouts),
			("sd_dm", d//16, outs),
			("sd_dqs", d//16, inouts)
			
		]:
			s = Signal(BV(width), name=name)
			setattr(self, name, s)
			l.append((name, s))
		
		self.dfi = dfi.Interface(a, ba, d, 2)
		ins += self.dfi.get_standard_names(True, False)
		outs += self.dfi.get_standard_names(False, True)
		
		self._inst = Instance("s6ddrphy",
			outs,
			ins,
			inouts,
			[
				("NUM_AD", a),
				("NUM_BA", ba),
				("NUM_D", d)
			],
			clkport="sys_clk")

	def get_fragment(self):
		return Fragment(instances=[self._inst])
