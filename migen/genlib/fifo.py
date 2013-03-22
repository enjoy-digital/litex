from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.fhdl.module import Module

def _inc(signal, modulo):
	if modulo == 2**len(signal):
		return signal.eq(signal + 1)
	else:
		return If(signal == (modulo - 1),
			signal.eq(0)
		).Else(
			signal.eq(signal + 1)
		)

class SyncFIFO(Module):
	def __init__(self, width, depth):
		self.din = Signal(width)
		self.we = Signal()
		self.writable = Signal() # not full
		self.dout = Signal(width)
		self.re = Signal()
		self.readable = Signal() # not empty

		###

		do_write = Signal()
		do_read = Signal()
		self.comb += [
			do_write.eq(self.writable & self.we),
			do_read.eq(self.readable & self.re)
		]

		level = Signal(max=depth+1)
		produce = Signal(max=depth)
		consume = Signal(max=depth)
		storage = Memory(width, depth)
		self.specials += storage

		wrport = storage.get_port(write_capable=True)
		self.comb += [
			wrport.adr.eq(produce),
			wrport.dat_w.eq(self.din),
			wrport.we.eq(do_write)
		]
		self.sync += If(do_write, _inc(produce, depth))

		rdport = storage.get_port(async_read=True)
		self.comb += [
			rdport.adr.eq(consume),
			self.dout.eq(rdport.dat_r)
		]
		self.sync += If(do_read, _inc(consume, depth))

		self.sync += [
			If(do_write,
				If(~do_read, level.eq(level + 1))
			).Elif(do_read,
				level.eq(level - 1)
			)
		]
		self.comb += [
			self.writable.eq(level != depth),
			self.readable.eq(level != 0)
		]
