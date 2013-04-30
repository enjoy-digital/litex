from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.fhdl.module import *
from migen.fhdl.tracer import get_obj_var_name

class _CSRBase(HUID):
	def __init__(self, size, name):
		HUID.__init__(self)
		self.name = get_obj_var_name(name)
		if self.name is None:
			raise ValueError("Cannot extract CSR name from code, need to specify.")
		if len(self.name) > 2 and self.name[:2] == "r_":
			self.name = self.name[2:]
		self.size = size

class CSR(_CSRBase):
	def __init__(self, size=1, name=None):
		_CSRBase.__init__(self, size, name)
		self.re = Signal(name=self.name + "_re")
		self.r = Signal(self.size, name=self.name + "_r")
		self.w = Signal(self.size, name=self.name + "_w")

class _CompoundCSR(_CSRBase, Module):
	def __init__(self, size, name):
		_CSRBase.__init__(self, size, name)
		self.simple_csrs = []

	def get_simple_csrs(self):
		if not self.finalized:
			raise FinalizeError
		return self.simple_csrs

	def do_finalize(self, busword):
		raise NotImplementedError

class CSRStatus(_CompoundCSR):
	def __init__(self, size=1, name=None):
		_CompoundCSR.__init__(self, size, name)
		self.status = Signal(self.size)

	def do_finalize(self, busword):
		nwords = (self.size + busword - 1)//busword
		for i in reversed(range(nwords)):
			nbits = min(self.size - i*busword, busword)
			sc = CSR(nbits, self.name + str(i) if nwords > 1 else self.name)
			self.comb += sc.w.eq(self.status[i*busword:i*busword+nbits])
			self.simple_csrs.append(sc)

class CSRStorage(_CompoundCSR):
	def __init__(self, size=1, reset=0, atomic_write=False, write_from_dev=False, alignment_bits=0, name=None):
		_CompoundCSR.__init__(self, size, name)
		self.alignment_bits = alignment_bits
		self.storage_full = Signal(self.size, reset=reset)
		self.storage = Signal(self.size - self.alignment_bits)
		self.comb += self.storage.eq(self.storage_full[self.alignment_bits:])
		self.atomic_write = atomic_write
		if write_from_dev:
			self.we = Signal()
			self.dat_w = Signal(self.size - self.alignment_bits)
			self.sync += If(self.we, self.storage_full.eq(self.dat_w << self.alignment_bits))

	def do_finalize(self, busword):
		nwords = (self.size + busword - 1)//busword
		if nwords > 1 and self.atomic_write:
			backstore = Signal(self.size - busword, name=self.name + "_backstore")
		for i in reversed(range(nwords)):
			nbits = min(self.size - i*busword, busword)
			sc = CSR(nbits, self.name + str(i) if nwords else self.name)
			self.simple_csrs.append(sc)
			lo = i*busword
			hi = lo+nbits
			# read
			if lo >= self.alignment_bits:
				self.comb += sc.w.eq(self.storage_full[lo:hi])
			elif hi > self.alignment_bits:
				self.comb += sc.w.eq(Cat(Replicate(0, hi - self.alignment_bits),
					self.storage_full[self.alignment_bits:hi]))
			else:
				self.comb += sc.w.eq(0)
			# write
			if nwords > 1 and self.atomic_write:
				if i:
					self.sync += If(sc.re, backstore[lo-busword:hi-busword].eq(sc.r))
				else:
					self.sync += If(sc.re, self.storage_full.eq(Cat(sc.r, backstore)))
			else:
				self.sync += If(sc.re, self.storage_full[lo:hi].eq(sc.r))

def csrprefix(prefix, csrs):
	for csr in csrs:
		csr.name = prefix + csr.name

def memprefix(prefix, memories):
	for memory in memories:
		memory.name_override = prefix + memory.name_override

class AutoCSR:
	def get_memories(self):
		r = []
		for k, v in self.__dict__.items():
			if isinstance(v, Memory):
				r.append(v)
			elif hasattr(v, "get_memories") and callable(v.get_memories):
				memories = v.get_memories()
				memprefix(k + "_", memories)
				r += memories
		return sorted(r, key=lambda x: x.huid)

	def get_csrs(self):
		r = []
		for k, v in self.__dict__.items():
			if isinstance(v, _CSRBase):
				r.append(v)
			elif hasattr(v, "get_csrs") and callable(v.get_csrs):
				csrs = v.get_csrs()
				csrprefix(k + "_", csrs)
				r += csrs
		return sorted(r, key=lambda x: x.huid)
