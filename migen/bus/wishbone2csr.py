from migen.bus import wishbone
from migen.bus import csr
from migen.fhdl.structure import *
from migen.corelogic.misc import timeline

class WB2CSR:
	def __init__(self):
		self.wishbone = wishbone.Interface()
		self.csr = csr.Interface()
	
	def get_fragment(self):
		sync = [
			self.csr.we.eq(0),
			self.csr.dat_w.eq(self.wishbone.dat_w[:8]),
			self.csr.adr.eq(self.wishbone.adr[:14]),
			self.wishbone.dat_r.eq(self.csr.dat_r)
		]
		sync += timeline(self.wishbone.cyc & self.wishbone.stb, [
			(1, [self.csr.we.eq(self.wishbone.we)]),
			(2, [self.wishbone.ack.eq(1)]),
			(3, [self.wishbone.ack.eq(0)])
		])
		return Fragment(sync=sync)
