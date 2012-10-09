from migen.fhdl.structure import *

class RegisterRaw:
	def __init__(self, name, size=1):
		self.name = name
		self.size = size
		self.re = Signal()
		self.r = Signal(BV(self.size))
		self.w = Signal(BV(self.size))

(READ_ONLY, WRITE_ONLY, READ_WRITE) = range(3)

class Field:
	def __init__(self, name, size=1, access_bus=READ_WRITE, access_dev=READ_ONLY, reset=0, atomic_write=False):
		self.name = name
		self.size = size
		self.access_bus = access_bus
		self.access_dev = access_dev
		self.storage = Signal(BV(self.size), reset=reset)
		self.atomic_write = atomic_write
		if self.access_bus == READ_ONLY and self.access_dev == WRITE_ONLY:
			self.w = Signal(BV(self.size))
		else:
			if self.access_dev == READ_ONLY or self.access_dev == READ_WRITE:
				self.r = Signal(BV(self.size))
			if self.access_dev == WRITE_ONLY or self.access_dev == READ_WRITE:
				self.w = Signal(BV(self.size))
				self.we = Signal()

class RegisterFields:
	def __init__(self, name, fields):
		self.name = name
		self.fields = fields

class RegisterField(RegisterFields):
	def __init__(self, name, size=1, access_bus=READ_WRITE, access_dev=READ_ONLY, reset=0, atomic_write=False):
		self.field = Field(name, size, access_bus, access_dev, reset, atomic_write)
		super().__init__(name, [self.field])

(ALIAS_NON_ATOMIC, ALIAS_ATOMIC_HOLD, ALIAS_ATOMIC_COMMIT) = range(3)

class FieldAlias:
	def __init__(self, mode, f, start, end, commit_list):
		self.mode = mode
		self.size = end - start
		self.access_bus = f.access_bus
		self.access_dev = f.access_dev
		if mode == ALIAS_ATOMIC_HOLD:
			self.storage = Signal(BV(end-start), name="atomic_hold")
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
						d.append(RegisterFields(reg.name, f))
						alias = FieldAlias(mode, field, top - slice2, top, commit_list)
						f = [alias]
						if mode == ALIAS_ATOMIC_HOLD:
							commit_list.append(alias)
						top -= slice2
						offset -= busword
				else:
					f.append(field)
			if f:
				d.append(RegisterFields(reg.name, f))
		else:
			raise TypeError
	return d
