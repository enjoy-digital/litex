from migen.fhdl.std import *
from migen.genlib.cdc import NoRetiming, MultiReg, GrayCounter
from migen.genlib.record import layout_len, Record

def _inc(signal, modulo):
	if modulo == 2**flen(signal):
		return signal.eq(signal + 1)
	else:
		return If(signal == (modulo - 1),
			signal.eq(0)
		).Else(
			signal.eq(signal + 1)
		)

class _FIFOInterface:
	def __init__(self, width_or_layout, depth):
		self.we = Signal()
		self.writable = Signal() # not full
		self.re = Signal()
		self.readable = Signal() # not empty

		if isinstance(width_or_layout, (int, tuple)):
			self.din = Signal(width_or_layout)
			self.dout = Signal(width_or_layout)
			self.din_bits = self.din
			self.dout_bits = self.dout
			self.width = width_or_layout
		else:
			self.din = Record(width_or_layout)
			self.dout = Record(width_or_layout)
			self.din_bits = self.din.raw_bits()
			self.dout_bits = self.dout.raw_bits()
			self.width = layout_len(width_or_layout)

class SyncFIFO(Module, _FIFOInterface):
	def __init__(self, width_or_layout, depth):
		_FIFOInterface.__init__(self, width_or_layout, depth)

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
		storage = Memory(self.width, depth)
		self.specials += storage

		wrport = storage.get_port(write_capable=True)
		self.specials += wrport
		self.comb += [
			wrport.adr.eq(produce),
			wrport.dat_w.eq(self.din_bits),
			wrport.we.eq(do_write)
		]
		self.sync += If(do_write, _inc(produce, depth))

		rdport = storage.get_port(async_read=True)
		self.specials += rdport
		self.comb += [
			rdport.adr.eq(consume),
			self.dout_bits.eq(rdport.dat_r)
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

class AsyncFIFO(Module, _FIFOInterface):
	def __init__(self, width_or_layout, depth):
		_FIFOInterface.__init__(self, width_or_layout, depth)

		###

		depth_bits = log2_int(depth, True)

		produce = RenameClockDomains(GrayCounter(depth_bits+1), "write")
		consume = RenameClockDomains(GrayCounter(depth_bits+1), "read")
		self.submodules += produce, consume
		self.comb += [
			produce.ce.eq(self.writable & self.we),
			consume.ce.eq(self.readable & self.re)
		]

		produce_rdomain = Signal(depth_bits+1)
		self.specials += [
			NoRetiming(produce.q),
			MultiReg(produce.q, produce_rdomain, "read")
		]
		consume_wdomain = Signal(depth_bits+1)
		self.specials += [
			NoRetiming(consume.q),
			MultiReg(consume.q, consume_wdomain, "write")
		]
		self.comb += [
			self.writable.eq((produce.q[-1] == consume_wdomain[-1])
			 | (produce.q[-2] == consume_wdomain[-2])
			 | (produce.q[:-2] != consume_wdomain[:-2])),
			self.readable.eq(consume.q != produce_rdomain)
		]

		storage = Memory(self.width, depth)
		self.specials += storage
		wrport = storage.get_port(write_capable=True, clock_domain="write")
		self.specials += wrport
		self.comb += [
			wrport.adr.eq(produce.q_binary[:-1]),
			wrport.dat_w.eq(self.din_bits),
			wrport.we.eq(produce.ce)
		]
		rdport = storage.get_port(clock_domain="read")
		self.specials += rdport
		self.comb += [
			rdport.adr.eq(consume.q_next_binary[:-1]),
			self.dout_bits.eq(rdport.dat_r)
		]

class _SyncFIFOTB(Module):
	def __init__(self):
		self.submodules.dut = SyncFIFO([("a", 32), ("b", 32)], 2)

		self.sync += [
			If(self.dut.we & self.dut.writable, 
				self.dut.din.a.eq(self.dut.din.a + 1),
				self.dut.din.b.eq(self.dut.din.b + 2)
			)
		]
		
	def do_simulation(self, s):
		s.wr(self.dut.we, s.cycle_counter % 4 == 0)
		s.wr(self.dut.re, s.cycle_counter % 3 == 0)
		print("readable: {0} re: {1} data: {2}/{3}".format(s.rd(self.dut.readable),
			s.rd(self.dut.re),
			s.rd(self.dut.dout.a), s.rd(self.dut.dout.b)))

def _main():
	from migen.sim.generic import Simulator
	Simulator(_SyncFIFOTB()).run(20)

if __name__ == "__main__":
	_main()
