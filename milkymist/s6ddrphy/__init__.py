from migen.fhdl.structure import *
from migen.bus import dfi

class S6DDRPHY:
	def __init__(self, a, ba, d):
		ins = []
		outs = []
		inouts = []
		
		for name in [
			"clk2x_90",
			"clk4x_wr_left",
			"clk4x_wr_strb_left",
			"clk4x_wr_right",
			"clk4x_wr_strb_right",
			"clk4x_rd_left",
			"clk4x_rd_strb_left",
			"clk4x_rd_right",
			"clk4x_rd_strb_right",
			"reset_n"
		]:
			s = Signal(name=name)
			setattr(self, name, s)
			ins.append((name, s))
		
		self._sd_pins = []
		sd_d = d//4
		for name, width, l in [
			("sd_clk_out_p", 1, outs),
			("sd_clk_out_n", 1, outs),
			("sd_a", a, outs),
			("sd_ba", ba, outs),
			("sd_cs_n", 1, outs),
			("sd_cke", 1, outs),
			("sd_ras_n", 1, outs),
			("sd_cas_n", 1, outs),
			("sd_we_n", 1, outs),
			("sd_dq", sd_d, inouts),
			("sd_dm", sd_d//8, outs),
			("sd_dqs", sd_d//8, inouts)
			
		]:
			s = Signal(BV(width), name=name)
			setattr(self, name, s)
			l.append((name, s))
			self._sd_pins.append(s)
		
		self.dfi = dfi.Interface(a, ba, d)
		ins += self.dfi.get_standard_names(True, False)
		outs += self.dfi.get_standard_names(False, True)
		
		ins += [
			("cfg_al", BV(3)),
			("cfg_cl", BV(3)),
			("cfg_bl", BV(2)),
			("cfg_regdimm", BV(1)),
			
			("init_done", BV(1)),
			
			("cpg_busy", BV(1)),
			
			("diag_dq_recal", BV(1)),
			("diag_io_sel", BV(9)),
			("diag_disable_cal_on_startup", BV(1)),
			("diag_cal_bits", BV(2)),
			("diag_short_cal", BV(1))
		]
		outs += [
			("phy_cal_done", BV(1)),
			
			("cpg_r_req", BV(1)),
			("cpg_w_req", BV(1)),
			("cpg_addr", BV(a)),
			("cpg_b_size", BV(4))
		]
		
		self._inst = Instance("spartan6_soft_phy",
			outs,
			ins,
			inouts,
			[
				("DSIZE", d),
				("NUM_AD", a),
				("NUM_BA", ba),
				("ADDR_WIDTH", 31),
				("DQ_IO_LOC", Constant(2**32-1, BV(32))),
				("DM_IO_LOC", Constant(2**4-1, BV(4)))
			],
			clkport="clk")

	def get_fragment(self):
		comb = [
			self._inst.ins["cfg_al"].eq(0),
			self._inst.ins["cfg_cl"].eq(3),
			self._inst.ins["cfg_bl"].eq(1),
			self._inst.ins["cfg_regdimm"].eq(0),
			
			self._inst.ins["diag_dq_recal"].eq(0),
			self._inst.ins["diag_io_sel"].eq(0),
			self._inst.ins["diag_disable_cal_on_startup"].eq(0),
			self._inst.ins["diag_cal_bits"].eq(0),
			self._inst.ins["diag_short_cal"].eq(0)
		]
		return Fragment(comb, instances=[self._inst], pads=set(self._sd_pins))
