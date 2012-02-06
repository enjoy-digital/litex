from migen.bus import wishbone
from migen.bus import csr
from migen.fhdl.structure import *
from migen.corelogic import timeline

class WB2CSR():
	def __init__(self):
		self.wishbone = wishbone.Slave()
		self.csr = csr.Master()
		self.timeline = timeline.Timeline(self.wishbone.cyc_i & self.wishbone.stb_i,
			[(1, [self.csr.we_o.eq(self.wishbone.we_i)]),
			(2, [self.wishbone.ack_o.eq(1)]),
			(3, [self.wishbone.ack_o.eq(0)])])
	
	def get_fragment(self):
		sync = [
			self.csr.we_o.eq(0),
			self.csr.d_o.eq(self.wishbone.dat_i[:8]),
			self.csr.a_o.eq(self.wishbone.adr_i[:14]),
			self.wishbone.dat_o.eq(self.csr.d_i)
		]
		return Fragment(sync=sync) + self.timeline.get_fragment()
