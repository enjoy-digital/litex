from migen.fhdl.structure import *
from migen.bus import wishbone

class SRAM:
	def __init__(self, depth):
		self.bus = wishbone.Interface()
		self.depth = depth
	
	def get_fragment(self):
		# memory
		mem = Memory(32, self.depth)
		port = mem.get_port(write_capable=True, we_granularity=8)
		# generate write enable signal
		comb = [port.we[i].eq(self.bus.cyc & self.bus.stb & self.bus.we & self.bus.sel[i])
			for i in range(4)]
		# address and data
		comb += [
			port.adr.eq(self.bus.adr[:len(port.adr)]),
			port.dat_w.eq(self.bus.dat_w),
			self.bus.dat_r.eq(port.dat_r)
		]
		# generate ack
		sync = [
			self.bus.ack.eq(0),
			If(self.bus.cyc & self.bus.stb & ~self.bus.ack,
				self.bus.ack.eq(1)
			)
		]
		return Fragment(comb, sync, memories=[mem])
