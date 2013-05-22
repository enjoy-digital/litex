from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus import csr
from migen.genlib.misc import timeline

class WB2CSR(Module):
	def __init__(self):
		self.wishbone = wishbone.Interface()
		self.csr = csr.Interface()
	
		###

		self.sync += [
			self.csr.we.eq(0),
			self.csr.dat_w.eq(self.wishbone.dat_w[:csr.data_width]),
			self.csr.adr.eq(self.wishbone.adr[:14]),
			self.wishbone.dat_r.eq(self.csr.dat_r)
		]
		self.sync += timeline(self.wishbone.cyc & self.wishbone.stb, [
			(1, [self.csr.we.eq(self.wishbone.we)]),
			(2, [self.wishbone.ack.eq(1)]),
			(3, [self.wishbone.ack.eq(0)])
		])
