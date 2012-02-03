from migen.fhdl.structure import *
from migen.bus import wishbone

class SRAM:
	def __init__(self, depth):
		self.bus = wishbone.Slave()
		self.depth = depth
	
	def get_fragment(self):
		# generate write enable signal
		we = Signal(BV(4))
		comb = [we[i].eq(self.bus.cyc_i & self.bus.stb_i & self.bus.we_i & self.bus.sel_i[3-i])
			for i in range(4)]
		# split address
		nbits = bits_for(self.depth-1)
		partial_adr = Signal(BV(nbits))
		comb.append(partial_adr.eq(self.bus.adr_i[:nbits]))
		# generate ack
		sync = [
			self.bus.ack_o.eq(0),
			If(self.bus.cyc_i & self.bus.stb_i & ~self.bus.ack_o,
				self.bus.ack_o.eq(1)
			)
		]
		# memory
		port = MemoryPort(partial_adr, self.bus.dat_o, we, self.bus.dat_i, we_granularity=8)
		return Fragment(comb, sync, memories=[Memory(32, self.depth, port)])
