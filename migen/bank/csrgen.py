from operator import itemgetter

from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank.description import *

class Bank:
	def __init__(self, description, address=0, bus=None):
		self.description = description
		self.address = address
		if bus is None:
			bus = csr.Interface()
		self.bus = bus
	
	def get_fragment(self):
		comb = []
		sync = []
		
		sel = Signal()
		comb.append(sel.eq(self.bus.adr[9:] == self.address))
		
		desc_exp = expand_description(self.description, csr.data_width)
		nbits = bits_for(len(desc_exp)-1)
		
		# Bus writes
		bwcases = {}
		for i, reg in enumerate(desc_exp):
			if isinstance(reg, RegisterRaw):
				comb.append(reg.r.eq(self.bus.dat_w[:reg.size]))
				comb.append(reg.re.eq(sel & \
					self.bus.we & \
					(self.bus.adr[:nbits] == i)))
			elif isinstance(reg, RegisterFields):
				bwra = []
				offset = 0
				for field in reg.fields:
					if field.access_bus == WRITE_ONLY or field.access_bus == READ_WRITE:
						bwra.append(field.storage.eq(self.bus.dat_w[offset:offset+field.size]))
					offset += field.size
				if bwra:
					bwcases[i] = bwra
				# commit atomic writes
				for field in reg.fields:
					if isinstance(field, FieldAlias) and field.commit_list:
						commit_instr = [hf.commit_to.eq(hf.storage) for hf in field.commit_list]
						sync.append(If(sel & self.bus.we & self.bus.adr[:nbits] == i, *commit_instr))
			else:
				raise TypeError
		if bwcases:
			sync.append(If(sel & self.bus.we, Case(self.bus.adr[:nbits], bwcases)))
		
		# Bus reads
		brcases = {}
		for i, reg in enumerate(desc_exp):
			if isinstance(reg, RegisterRaw):
				brcases[i] = [self.bus.dat_r.eq(reg.w)]
			elif isinstance(reg, RegisterFields):
				brs = []
				reg_readable = False
				for field in reg.fields:
					if field.access_bus == READ_ONLY or field.access_bus == READ_WRITE:
						brs.append(field.storage)
						reg_readable = True
					else:
						brs.append(Replicate(0, field.size))
				if reg_readable:
					brcases[i] = [self.bus.dat_r.eq(Cat(*brs))]
			else:
				raise TypeError
		if brcases:
			sync.append(self.bus.dat_r.eq(0))
			sync.append(If(sel, Case(self.bus.adr[:nbits], brcases)))
		else:
			comb.append(self.bus.dat_r.eq(0))
		
		# Device access
		for reg in self.description:
			if isinstance(reg, RegisterFields):
				for field in reg.fields:
					if field.access_bus == READ_ONLY and field.access_dev == WRITE_ONLY:
						comb.append(field.storage.eq(field.w))
					else:
						if field.access_dev == READ_ONLY or field.access_dev == READ_WRITE:
							comb.append(field.r.eq(field.storage))
						if field.access_dev == WRITE_ONLY or field.access_dev == READ_WRITE:
							sync.append(If(field.we, field.storage.eq(field.w)))
		
		return Fragment(comb, sync)

# address_map(name, memory) returns the CSR offset at which to map
# the CSR object (register bank or memory).
# If memory=None, the object is the register bank of object source.name.
# Otherwise, it is a memory object belonging to source.name.
# address_map is called exactly once for each object at each call to
# scan(), so it can have side effects.
class BankArray:
	def __init__(self, source, address_map):
		self.source = source
		self.address_map = address_map
		self.scan()

	def scan(self):
		self.banks = []
		self.srams = []
		for name, obj in sorted(self.source.__dict__.items(), key=itemgetter(0)):
			if hasattr(obj, "get_registers"):
				registers = obj.get_registers()
			else:
				registers = []
			if hasattr(obj, "get_memories"):
				memories = obj.get_memories()
				for memory in memories:
					mapaddr = self.address_map(name, memory)
					mmap = csr.SRAM(memory, mapaddr)
					registers += mmap.get_registers()
					self.srams.append((name, memory, mmap))
			if registers:
				mapaddr = self.address_map(name, None)
				rmap = Bank(registers, mapaddr)
				self.banks.append((name, rmap))

	def get_rmaps(self):
		return [rmap for name, rmap in self.banks]

	def get_mmaps(self):
		return [mmap for name, memory, mmap in self.srams]

	def get_buses(self):
		return [i.bus for i in self.get_rmaps() + self.get_mmaps()]

	def get_fragment(self):
		return sum([i.get_fragment() for i in self.get_rmaps() + self.get_mmaps()], Fragment())
