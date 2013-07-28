from migen.fhdl.std import *
from migen.bus.transactions import *
from migen.bank.description import CSRStorage
from migen.genlib.record import *
from migen.genlib.misc import chooser

_layout = [
	("adr",		14,				DIR_M_TO_S),
	("we",		1,				DIR_M_TO_S),
	("dat_w",	"data_width",	DIR_M_TO_S),
	("dat_r",	"data_width",	DIR_S_TO_M)
]

class Interface(Record):
	def __init__(self, data_width=8):
		Record.__init__(self, _layout, data_width=data_width)

class Interconnect(Module):
	def __init__(self, master, slaves):
		self.comb += master.connect(*slaves)

class Initiator(Module):
	def __init__(self, generator, bus=None):
		self.generator = generator
		if bus is None:
			bus = Interface()
		self.bus = bus
		self.transaction = None
		self.read_data_ready = False
		self.done = False
		
	def do_simulation(self, s):
		if not self.done:
			if self.transaction is not None:
				if isinstance(self.transaction, TRead):
					if self.read_data_ready:
						self.transaction.data = s.rd(self.bus.dat_r)
						self.transaction = None
						self.read_data_ready = False
					else:
						self.read_data_ready = True
				else:
					s.wr(self.bus.we, 0)
					self.transaction = None
			if self.transaction is None:
				try:
					self.transaction = next(self.generator)
				except StopIteration:
					self.transaction = None
					self.done = True
				if self.transaction is not None:
					s.wr(self.bus.adr, self.transaction.address)
					if isinstance(self.transaction, TWrite):
						s.wr(self.bus.we, 1)
						s.wr(self.bus.dat_w, self.transaction.data)

class SRAM(Module):
	def __init__(self, mem_or_size, address, read_only=None, init=None, bus=None):
		if bus is None:
			bus = Interface()
		self.bus = bus
		data_width = flen(self.bus.dat_w)
		if isinstance(mem_or_size, Memory):
			mem = mem_or_size
		else:
			mem = Memory(data_width, mem_or_size//(data_width//8), init=init)
		csrw_per_memw = (mem.width + data_width - 1)//data_width
		word_bits = log2_int(csrw_per_memw)
		page_bits = log2_int((mem.depth*csrw_per_memw + 511)//512, False)
		if page_bits:
			self._page = CSRStorage(page_bits, name=mem.name_override + "_page")
		else:
			self._page = None
		if read_only is None:
			if hasattr(mem, "bus_read_only"):
				read_only = mem.bus_read_only
			else:
				read_only = False
	
		###

		port = mem.get_port(write_capable=not read_only)
		self.specials += mem, port
		
		sel = Signal()
		sel_r = Signal()
		self.sync += sel_r.eq(sel)
		self.comb += sel.eq(self.bus.adr[9:] == address)

		if word_bits:
			word_index = Signal(word_bits)
			word_expanded = Signal(csrw_per_memw*data_width)
			self.sync += word_index.eq(self.bus.adr[:word_bits])
			self.comb += [
				word_expanded.eq(port.dat_r),
				If(sel_r,
					chooser(word_expanded, word_index, self.bus.dat_r, n=csrw_per_memw, reverse=True)
				)
			]
			if not read_only:
				wregs = []
				for i in range(csrw_per_memw-1):
					wreg = Signal(data_width)
					self.sync += If(sel & self.bus.we & (self.bus.adr[:word_bits] == i), wreg.eq(self.bus.dat_w))
					wregs.append(wreg)
				memword_chunks = [self.bus.dat_w] + list(reversed(wregs))
				self.comb += [
					port.we.eq(sel & self.bus.we & (self.bus.adr[:word_bits] == csrw_per_memw - 1)),
					port.dat_w.eq(Cat(*memword_chunks))
				]
		else:
			self.comb += If(sel_r, self.bus.dat_r.eq(port.dat_r))
			if not read_only:
				self.comb += [
					port.we.eq(sel & self.bus.we),
					port.dat_w.eq(self.bus.dat_w)
				]
		
		if self._page is None:
			self.comb += port.adr.eq(self.bus.adr[word_bits:word_bits+flen(port.adr)])
		else:
			pv = self._page.storage
			self.comb += port.adr.eq(Cat(self.bus.adr[word_bits:word_bits+flen(port.adr)-flen(pv)], pv))

	def get_csrs(self):
		if self._page is None:
			return []
		else:
			return [self._page]
