from functools import partial

from migen.fhdl.structure import *
from migen.bus import wishbone
from migen.corelogic import timeline

class Inst:
	def __init__(self, adr_width, rd_timing):
		self.bus = wishbone.Slave("norflash")
		d = partial(declare_signal, self)
		d("adr", BV(adr_width-1))
		d("d", BV(16))
		d("oe_n")
		d("we_n")
		d("ce_n")
		self.timeline = timeline.Inst(self.bus.cyc_i & self.bus.stb_i,
			[(0, [self.adr.eq(Cat(0, self.bus.adr_i[2:adr_width]))]),
			(rd_timing, [
				self.bus.dat_o[16:].eq(self.d),
				self.adr.eq(Cat(1, self.bus.adr_i[2:adr_width]))]),
			(2*rd_timing, [
				self.bus.dat_o[:16].eq(self.d),
				self.bus.ack_o.eq(1)]),
			(2*rd_timing+1, [
				self.bus.ack_o.eq(0)])])
	
	def get_fragment(self):
		comb = [self.oe_n.eq(0), self.we_n.eq(1),
			self.ce_n.eq(0)]
		return Fragment(comb, pads={self.adr, self.d, self.oe_n, self.we_n, self.ce_n}) \
			+ self.timeline.get_fragment()
