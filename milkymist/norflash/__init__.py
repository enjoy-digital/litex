from migen.fhdl.structure import *
from migen.bus import wishbone
from migen.genlib.misc import timeline

class NorFlash:
	def __init__(self, adr_width, rd_timing):
		self.adr_width = adr_width
		self.rd_timing = rd_timing
		
		self.bus = wishbone.Interface()
		self.adr = Signal(adr_width-1)
		self.d = Signal(16)
		self.oe_n = Signal()
		self.we_n = Signal()
		self.ce_n = Signal()
	
	def get_fragment(self):
		comb = [self.oe_n.eq(0), self.we_n.eq(1),
			self.ce_n.eq(0)]
		sync = timeline(self.bus.cyc & self.bus.stb, [
			(0, [self.adr.eq(Cat(0, self.bus.adr[:self.adr_width-2]))]),
			(self.rd_timing, [
				self.bus.dat_r[16:].eq(self.d),
				self.adr.eq(Cat(1, self.bus.adr[:self.adr_width-2]))]),
			(2*self.rd_timing, [
				self.bus.dat_r[:16].eq(self.d),
				self.bus.ack.eq(1)]),
			(2*self.rd_timing + 1, [
				self.bus.ack.eq(0)])
		])
		return Fragment(comb, sync)
