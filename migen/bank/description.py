from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.fhdl.tracer import get_obj_var_name

class _Register(HUID):
	def __init__(self, name):
		HUID.__init__(self)
		self.name = get_obj_var_name(name)
		if self.name is None:
			raise ValueError("Cannot extract register name from code, need to specify.")
		if len(self.name) > 2 and self.name[:2] == "r_":
			self.name = self.name[2:]

class RegisterRaw(_Register):
	def __init__(self, size=1, name=None):
		_Register.__init__(self, name)
		self.size = size
		self.re = Signal()
		self.r = Signal(self.size)
		self.w = Signal(self.size)

	def get_size(self):
		return self.size

(READ_ONLY, WRITE_ONLY, READ_WRITE) = range(3)

class Field:
	def __init__(self, size=1, access_bus=READ_WRITE, access_dev=READ_ONLY, reset=0, atomic_write=False, name=None):
		self.name = get_obj_var_name(name)
		if self.name is None:
			raise ValueError("Cannot extract field name from code, need to specify.")
		self.size = size
		self.access_bus = access_bus
		self.access_dev = access_dev
		self.storage = Signal(self.size, reset=reset)
		self.atomic_write = atomic_write
		if self.access_bus == READ_ONLY and self.access_dev == WRITE_ONLY:
			self.w = Signal(self.size)
		else:
			if self.access_dev == READ_ONLY or self.access_dev == READ_WRITE:
				self.r = Signal(self.size, reset=reset)
			if self.access_dev == WRITE_ONLY or self.access_dev == READ_WRITE:
				self.w = Signal(self.size)
				self.we = Signal()

class RegisterFields(_Register):
	def __init__(self, *fields, name=None):
		_Register.__init__(self, name)
		self.fields = fields

	def get_size(self):
		return sum(field.size for field in self.fields)

class RegisterField(RegisterFields):
	def __init__(self, size=1, access_bus=READ_WRITE, access_dev=READ_ONLY, reset=0, atomic_write=False, name=None):
		self.field = Field(size, access_bus, access_dev, reset, atomic_write, name="")
		RegisterFields.__init__(self, self.field, name=name)

def regprefix(prefix, registers):
	for register in registers:
		register.name = prefix + register.name

def memprefix(prefix, memories):
	for memory in memories:
		memory.name_override = prefix + memory.name_override

class AutoReg:
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

	def get_registers(self):
		r = []
		for k, v in self.__dict__.items():
			if isinstance(v, _Register):
				r.append(v)
			elif hasattr(v, "get_registers") and callable(v.get_registers):
				registers = v.get_registers()
				regprefix(k + "_", registers)
				r += registers
		return sorted(r, key=lambda x: x.huid)

(ALIAS_NON_ATOMIC, ALIAS_ATOMIC_HOLD, ALIAS_ATOMIC_COMMIT) = range(3)

class FieldAlias:
	def __init__(self, mode, f, start, end, commit_list):
		self.mode = mode
		self.size = end - start
		self.access_bus = f.access_bus
		self.access_dev = f.access_dev
		if mode == ALIAS_ATOMIC_HOLD:
			self.storage = Signal(end-start, name="atomic_hold")
			self.commit_to = f.storage[start:end]
		else:
			self.storage = f.storage[start:end]
		if mode == ALIAS_ATOMIC_COMMIT:
			self.commit_list = commit_list
		else:
			self.commit_list = []
		# device access is through the original field

def expand_description(description, busword):
	d = []
	for reg in description:
		if isinstance(reg, RegisterRaw):
			if reg.size > busword:
				raise ValueError("Raw register larger than a bus word")
			d.append(reg)
		elif isinstance(reg, RegisterFields):
			f = []
			offset = 0
			totalsize = 0
			for field in reg.fields:
				offset += field.size
				totalsize += field.size
				if offset > busword:
					# add padding
					padding = busword - (totalsize % busword)
					if padding != busword:
						totalsize += padding
						offset += padding
					
					top = field.size
					commit_list = []
					while offset > busword:
						if field.atomic_write:
							if offset - busword > busword:
								mode = ALIAS_ATOMIC_HOLD
							else:
								# last iteration
								mode = ALIAS_ATOMIC_COMMIT
						else:
							mode = ALIAS_NON_ATOMIC
						
						slice1 = busword - offset + top
						slice2 = min(offset - busword, busword)
						if slice1:
							alias = FieldAlias(mode, field, top - slice1, top, commit_list)
							f.append(alias)
							if mode == ALIAS_ATOMIC_HOLD:
								commit_list.append(alias)
							top -= slice1
						d.append(RegisterFields(*f, name=reg.name))
						alias = FieldAlias(mode, field, top - slice2, top, commit_list)
						f = [alias]
						if mode == ALIAS_ATOMIC_HOLD:
							commit_list.append(alias)
						top -= slice2
						offset -= busword
				else:
					f.append(field)
			if f:
				d.append(RegisterFields(*f, name=reg.name))
		else:
			raise TypeError
	return d
