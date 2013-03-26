from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bus import wishbone
from migen.genlib.misc import timeline

class NorFlash(Module):
	def __init__(self, pads, rd_timing):
		self.bus = wishbone.Interface()
	
		###

		adr_width = len(pads.adr) + 1
		self.comb += [pads.oe_n.eq(0), pads.we_n.eq(1),
			pads.ce_n.eq(0)]
		self.sync += timeline(self.bus.cyc & self.bus.stb, [
			(0, [pads.adr.eq(Cat(0, self.bus.adr[:adr_width-2]))]),
			(rd_timing, [
				self.bus.dat_r[16:].eq(pads.d),
				pads.adr.eq(Cat(1, self.bus.adr[:adr_width-2]))]),
			(2*rd_timing, [
				self.bus.dat_r[:16].eq(pads.d),
				self.bus.ack.eq(1)]),
			(2*rd_timing + 1, [
				self.bus.ack.eq(0)])
		])
