import csv

class MappedReg:
	def __init__(self, readfn, writefn, name, addr, length, busword, mode):
		self.readfn = readfn
		self.writefn = writefn
		self.addr = addr
		self.length = length
		self.busword = busword
		self.mode = mode

	def read(self):
		if self.mode not in ["rw", "ro"]:
			raise KeyError(name + "register not readable")
		r = 0
		for i in range(self.length):
			r |= self.readfn(self.addr + 4*i)
			if i != (self.length-1):
				r <<= self.busword
		return r

	def write(self, value):
		if self.mode not in ["rw", "wo"]:
			raise KeyError(name + "register not writable")
		for i in range(self.length):
			dat = (value >> ((self.length-1-i)*self.busword)) & (2**self.busword-1)
			self.writefn(self.addr + 4*i, dat)

class MappedRegs:
	def __init__(self, d):
		self.d = d

	def __getattr__(self, attr):
		try:
			return self.__dict__['d'][attr]
		except KeyError:
			pass

		raise KeyError("No such register " + attr)

def	build_map(addrmap, busword, readfn, writefn):
	csv_reader = csv.reader(open(addrmap), delimiter=',', quotechar='#')
	d = {}
	for item in csv_reader:
		name, addr, length, mode = item
		addr = int(addr.replace("0x", ""), 16)
		length = int(length)
		d[name] = MappedReg(readfn, writefn, name, addr, length, busword, mode)
	return MappedRegs(d)