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
	def __init__(self, name, size=1, access_bus=READ_WRITE, access_dev=READ_ONLY, reset=0):
		self.name = name
		self.size = size
		self.access_bus = access_bus
		self.access_dev = access_dev
		self.storage = Signal(BV(self.size), reset=reset)
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
	def __init__(self, name, size=1, access_bus=READ_WRITE, access_dev=READ_ONLY, reset=0):
		self.field = Field(name, size, access_bus, access_dev, reset)
		RegisterFields.__init__(self, name, [self.field])

class FieldAlias:
	def __init__(self, f, start, end):
		self.size = end - start
		self.access_bus = f.access_bus
		self.access_dev = f.access_dev
		self.storage = f.storage[start:end]
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
			size = 0
			for field in reg.fields:
				size += field.size
				if size > busword:
					top = field.size
					while size > busword:
						slice1 = busword - size + top
						slice2 = min(size - busword, busword)
						if slice1:
							f.append(FieldAlias(field, top - slice1, top))
							top -= slice1
						d.append(RegisterFields(reg.name, f))
						f = [FieldAlias(field, top - slice2, top)]
						top -= slice2
						size -= busword
				else:
					f.append(field)
			if f:
				d.append(RegisterFields(reg.name, f))
		else:
			raise TypeError
	return d
