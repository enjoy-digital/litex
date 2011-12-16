from migen.fhdl import structure as f

class Register:
	def __init__(self, name):
		self.name = name
		self.fields = []
	
	def add_field(self, f):
		self.fields.append(f)

(READ_ONLY, WRITE_ONLY, READ_WRITE) = range(3)

class Field:
	def __init__(self, parent, name, size=1, access_bus=READ_WRITE, access_dev=READ_ONLY, reset=0):
		self.parent = parent
		self.name = name
		self.size = size
		self.access_bus = access_bus
		self.access_dev = access_dev
		self.reset = reset
		fullname = parent.name + "_" + name
		self.storage = f.Signal(f.BV(self.size), fullname)
		if self.access_dev == READ_ONLY or self.access_dev == READ_WRITE:
			self.dev_r = f.Signal(f.BV(self.size), fullname + "_r")
		if self.access_dev == WRITE_ONLY or self.access_dev == READ_WRITE:
			self.dev_w = f.Signal(f.BV(self.size), fullname + "_w")
			self.dev_we = f.Signal(name=fullname + "_we")
		self.parent.add_field(self)