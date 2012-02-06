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
