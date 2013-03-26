from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module
from migen.bus import dfi

class S6DDRPHY(Module):
	def __init__(self, pads):
		self.dfi = dfi.Interface(len(pads.a), len(pads.ba), 2*len(pads.dq), 2)
		self.clk4x_wr_strb = Signal()
		self.clk4x_rd_strb = Signal()

		###

		inst_items = [
			Instance.Parameter("NUM_AD", len(pads.a)),
			Instance.Parameter("NUM_BA", len(pads.ba)),
			Instance.Parameter("NUM_D", 2*len(pads.dq)),

			Instance.Input("sys_clk", ClockSignal()),
			Instance.Input("clk2x_270", ClockSignal("sys2x_270")),
			Instance.Input("clk4x_wr", ClockSignal("sys4x_wr")),
			Instance.Input("clk4x_rd", ClockSignal("sys4x_rd")),

			Instance.Input("clk4x_wr_strb", self.clk4x_wr_strb),
			Instance.Input("clk4x_rd_strb", self.clk4x_rd_strb),

			Instance.Output("sd_a", pads.a),
			Instance.Output("sd_ba", pads.ba),
			Instance.Output("sd_cs_n", pads.cs_n),
			Instance.Output("sd_cke", pads.cke),
			Instance.Output("sd_ras_n", pads.ras_n),
			Instance.Output("sd_cas_n", pads.cas_n),
			Instance.Output("sd_we_n", pads.we_n),
			Instance.InOut("sd_dq", pads.dq),
			Instance.Output("sd_dm", pads.dm),
			Instance.InOut("sd_dqs", pads.dqs)
		]
		inst_items += [Instance.Input(name, signal) 
			for name, signal in self.dfi.get_standard_names(True, False)]
		inst_items += [Instance.Output(name, signal)
			for name, signal in self.dfi.get_standard_names(False, True)]
		self.specials += Instance("s6ddrphy", *inst_items)
