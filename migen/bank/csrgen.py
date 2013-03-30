from operator import itemgetter

from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bus import csr
from migen.bank.description import *

class Bank(Module):
	def __init__(self, description, address=0, bus=None):
		if bus is None:
			bus = csr.Interface()
		self.bus = bus
		
		###

		if not description:
			return
		
		# Turn description into simple CSRs and claim ownership of compound CSR modules
		simple_csrs = []
		for c in description:
			if isinstance(c, CSR):
				simple_csrs.append(c)
			else:
				c.finalize(csr.data_width)
				simple_csrs += c.get_simple_csrs()
				self.submodules += c
		nbits = bits_for(len(simple_csrs)-1)

		# Decode selection
		sel = Signal()
		self.comb += sel.eq(self.bus.adr[9:] == address)
		
		# Bus writes
		for i, c in enumerate(simple_csrs):
			self.comb += [
				c.r.eq(self.bus.dat_w[:c.size]),
				c.re.eq(sel & \
					self.bus.we & \
					(self.bus.adr[:nbits] == i))
			]
		
		# Bus reads
		brcases = dict((i, self.bus.dat_r.eq(c.w)) for i, c in enumerate(simple_csrs))
		self.sync += [
			self.bus.dat_r.eq(0),
			If(sel, Case(self.bus.adr[:nbits], brcases))
		]

# address_map(name, memory) returns the CSR offset at which to map
# the CSR object (register bank or memory).
# If memory=None, the object is the register bank of object source.name.
# Otherwise, it is a memory object belonging to source.name.
# address_map is called exactly once for each object at each call to
# scan(), so it can have side effects.
class BankArray(Module):
	def __init__(self, source, address_map):
		self.source = source
		self.address_map = address_map
		self.scan()

	def scan(self):
		self.banks = []
		self.srams = []
		for name, obj in sorted(self.source.__dict__.items(), key=itemgetter(0)):
			if hasattr(obj, "get_csrs"):
				csrs = obj.get_csrs()
			else:
				csrs = []
			if hasattr(obj, "get_memories"):
				memories = obj.get_memories()
				for memory in memories:
					mapaddr = self.address_map(name, memory)
					mmap = csr.SRAM(memory, mapaddr)
					self.submodules += mmap
					csrs += mmap.get_csrs()
					self.srams.append((name, memory, mapaddr, mmap))
			if csrs:
				mapaddr = self.address_map(name, None)
				rmap = Bank(csrs, mapaddr)
				self.submodules += rmap
				self.banks.append((name, csrs, mapaddr, rmap))

	def get_rmaps(self):
		return [rmap for name, csrs, mapaddr, rmap in self.banks]

	def get_mmaps(self):
		return [mmap for name, memory, mapaddr, mmap in self.srams]

	def get_buses(self):
		return [i.bus for i in self.get_rmaps() + self.get_mmaps()]
