from migen.fhdl.std import *
from migen.genlib.misc import optree
from migen.actorlib.crc import CRCInserter, CRCChecker

from lib.sata.std import *

class CRCEngine(Module):
	"""Cyclic Redundancy Check Engine

	Compute next CRC value from last CRC value and data input using
	an optimized asynchronous LFSR.

	Parameters
	----------
	width : int
		Width of the data bus and CRC.
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
	def __init__(self, width, polynom):
		self.d = Signal(width)
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

		new = Signal(32)
		self.comb += new.eq(self.last ^ self.d)

		# compute and optimize CRC's LFSR
		curval = [[("new", i)] for i in range(width)]
		for i in range(width):
			feedback = curval.pop()
			for j in range(width-1):
				if (polynom & (1<<(j+1))):
					curval[j] += feedback
				curval[j] = _optimize_eq(curval[j])
			curval.insert(0, feedback)

		# implement logic
		for i in range(width):
			xors = []
			for t, n in curval[i]:
				if t == "new":
					xors += [new[n]]
			self.comb += self.next[i].eq(optree("^", xors))

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class SATACRC(Module):
	"""SATA CRC

	Implement a SATA CRC generator/checker

	Attributes
	----------
	value : out
		CRC value (used for generator).
	error : out
		CRC error (used for checker).
	"""
	width = 32
	polynom = 0x04C11DB7
	init = 0x52325032
	check = 0xC704DD7B
	def __init__(self, dat_width):
		self.d = Signal(self.width)
		self.value = Signal(self.width)
		self.error = Signal()

		###

		self.submodules.engine = CRCEngine(self.width, self.polynom)
		reg_i = Signal(self.width, reset=self.init)
		self.sync += reg_i.eq(self.engine.next)
		self.comb += [
			self.engine.d.eq(self.d),
			self.engine.last.eq(reg_i),

			self.value.eq(reg_i),
			self.error.eq(self.engine.next != self.check)
		]

class SATACRCInserter(CRCInserter):
	def __init__(self, layout):
		CRCInserter.__init__(self, SATACRC, layout)

class SATACRCChecker(CRCChecker):
	def __init__(self, layout):
		CRCChecker.__init__(self, SATACRC, layout)