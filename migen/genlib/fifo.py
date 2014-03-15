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
	"""
	Data written to the input interface (`din`, `we`, `writable`) is
	buffered and can be read at the output interface (`dout`, `re`,
	`readable`). The data entry written first to the input 
	also appears first on the output.

	Parameters
	----------
	width_or_layout : int, layout
		Bit width or `Record` layout for the data.
	depth : int
		Depth of the FIFO.

	Attributes
	----------
	din : in, width_or_layout
		Input data either flat or Record structured.
	writable : out
		There is space in the FIFO and `we` can be asserted to load new data.
	we : in
		Write enable signal to latch `din` into the FIFO. Does nothing if
		`writable` is not asserted.
	dout : out, width_or_layout
		Output data, same type as `din`. Only valid if `readable` is
		asserted.
	readable : out
		Output data `dout` valid, FIFO not empty.
	re : in
		Acknowledge `dout`. If asserted, the next entry will be
		available on the next cycle (if `readable` is high then).
	"""
	def __init__(self, width_or_layout, depth):
		self.we = Signal()
		self.writable = Signal() # not full
		self.re = Signal()
		self.readable = Signal() # not empty

		if isinstance(width_or_layout, list):
			self.din = Record(width_or_layout)
			self.dout = Record(width_or_layout)
			self.din_bits = self.din.raw_bits()
			self.dout_bits = self.dout.raw_bits()
			self.width = layout_len(width_or_layout)
		else:
			self.din = Signal(width_or_layout)
			self.dout = Signal(width_or_layout)
			self.din_bits = self.din
			self.dout_bits = self.dout
			self.width = width_or_layout

class SyncFIFO(Module, _FIFOInterface):
	"""Synchronous FIFO (first in, first out)

	Read and write interfaces are accessed from the same clock domain.
	If different clock domains are needed, use :class:`AsyncFIFO`.

	{interface}
	level : out
		Number of unread entries.
	flush : in
		Flush the FIFO discarding pending write.
		In the next cycle `readable` will be deasserted
		and `writable` will be asserted, `level` will be zero.
	"""
	__doc__ = __doc__.format(interface=_FIFOInterface.__doc__)

	def __init__(self, width_or_layout, depth):
		_FIFOInterface.__init__(self, width_or_layout, depth)

		self.flush = Signal()
		self.level = Signal(max=depth+1)

		###

		do_write = Signal()
		do_read = Signal()
		self.comb += [
			do_write.eq(self.writable & self.we),
			do_read.eq(self.readable & self.re)
		]

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
			If(self.flush,
				produce.eq(0),
				consume.eq(0),
				self.level.eq(0),
			).Elif(do_write,
				If(~do_read, self.level.eq(self.level + 1))
			).Elif(do_read,
				self.level.eq(self.level - 1)
			)
		]
		self.comb += [
			self.writable.eq(self.level != depth),
			self.readable.eq(self.level != 0)
		]

class AsyncFIFO(Module, _FIFOInterface):
	"""Asynchronous FIFO (first in, first out)

	Read and write interfaces are accessed from different clock domains,
	named `read` and `write`. Use `RenameClockDomains` to rename to
	other names.

	{interface}
	"""
	__doc__ = __doc__.format(interface=_FIFOInterface.__doc__)

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
