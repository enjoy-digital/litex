from migen.fhdl.structure import *
from migen.bus import wishbone

class SRAM:
	def __init__(self, depth):
		self.bus = wishbone.Interface()
		self.depth = depth
	
	def get_fragment(self):
		# generate write enable signal
		we = Signal(BV(4))
		comb = [we[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])
			for i in range(4)]
		# split address
		nbits = bits_for(self.depth-1)
		partial_adr = Signal(BV(nbits))
		comb.append(partial_adr.eq(self.bus.adr[:nbits]))
		# generate ack
		sync = [
			self.bus.ack.eq(0),
			If(self.bus.cyc & self.bus.stb & ~self.bus.ack,
				self.bus.ack.eq(1)
			)
		]
		# memory
		port = MemoryPort(partial_adr, self.bus.dat_r, we, self.bus.dat_w, we_granularity=8)
		return Fragment(comb, sync, memories=[Memory(32, self.depth, port)])
