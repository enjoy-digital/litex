from migen.fhdl import structure as f
from migen.bus import wishbone
from migen.corelogic import timeline
from functools import partial

class Inst:
	def __init__(self, adr_width, rd_timing):
		self.bus = wishbone.Slave("norflash")
		d = partial(f.Declare, self)
		d("adr", f.BV(adr_width-1))
		d("d", f.BV(16))
		d("oe_n")
		d("we_n")
		d("ce_n")
		d("rst_n")
		self.timeline = timeline.Inst(self.bus.cyc_i & self.bus.stb_i,
			[(0, [f.Assign(self.adr, f.Cat(0, self.bus.adr_i[2:adr_width]))]),
			(rd_timing, [
				f.Assign(self.bus.dat_o[16:], self.d),
				f.Assign(self.adr, f.Cat(1, self.bus.adr_i[2:adr_width]))]),
			(2*rd_timing, [
				f.Assign(self.bus.dat_o[:16], self.d),
				f.Assign(self.bus.ack_o, 1)]),
			(2*rd_timing+1, [
				f.Assign(self.bus.ack_o, 0)])])
	
	def GetFragment(self):
		comb = [f.Assign(self.oe_n, 0), f.Assign(self.we_n, 1),
			f.Assign(self.ce_n, 0), f.Assign(self.rst_n, 1)]
		return f.Fragment(comb, pads={self.adr, self.d, self.oe_n, self.we_n, self.ce_n, self.rst_n}) \
			+ self.timeline.GetFragment()
