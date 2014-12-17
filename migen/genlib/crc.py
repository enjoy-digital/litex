from migen.fhdl.std import *
from migen.genlib.misc import optree

class CRCEngine(Module):
	"""Cyclic Redundancy Check Engine

	Compute next CRC value from last CRC value and data input using
	an optimized asynchronous LFSR.

	Parameters
	----------
	dat_width : int
		Width of the data bus.
	width : int
		Width of the CRC.
	polynom : int
		Polynom of the CRC (ex: 0x04C11DB7 for IEEE 802.3 CRC)

	Attributes
	----------
	d : in
		Data input.
	last : in
		last CRC value.
	next :
		next CRC value.
	"""
	def __init__(self, dat_width, width, polynom):
		self.d = Signal(dat_width)
		self.last = Signal(width)
		self.next = Signal(width)

		###

		def _optimize_eq(l):
			"""
			Replace even numbers of XORs in the equation
			with an equivalent XOR
			"""
			d = {}
			for e in l:
				if e in d:
					d[e] += 1
				else:
					d[e] = 1
			r = []
			for key, value in d.items():
				if value%2 != 0:
					r.append(key)
			return r

		# compute and optimize CRC's LFSR
		curval = [[("state", i)] for i in range(width)]
		for i in range(dat_width):
			feedback = curval.pop() + [("din", i)]
			for j in range(width-1):
				if (polynom & (1<<(j+1))):
					curval[j] += feedback
				curval[j] = _optimize_eq(curval[j])
			curval.insert(0, feedback)

		# implement logic
		for i in range(width):
			xors = []
			for t, n in curval[i]:
				if t == "state":
					xors += [self.last[n]]
				elif t == "din":
					xors += [self.d[n]]
			self.comb += self.next[i].eq(optree("^", xors))

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class CRC32(Module):
	"""IEEE 802.3 CRC

	Implement an IEEE 802.3 CRC generator/checker.

	Parameters
	----------
	dat_width : int
		Width of the data bus.

	Attributes
	----------
	d : in
		Data input.
	value : out
		CRC value (used for generator).
	error : out
		CRC error (used for checker).
	"""
	width = 32
	polynom = 0x04C11DB7
	init = 2**width-1
	check = 0xC704DD7B
	def __init__(self, dat_width):
		self.d = Signal(dat_width)
		self.value = Signal(self.width)
		self.error = Signal()

		###

		self.submodules.engine = CRCEngine(dat_width, self.width, self.polynom)
		reg = Signal(self.width, reset=self.init)
		self.sync += reg.eq(self.engine.next)
		self.comb += [
			self.engine.d.eq(self.d),
			self.engine.last.eq(reg),

			self.value.eq(~reg[::-1]),
			self.error.eq(self.engine.next != self.check)
		]
