from collections import OrderedDict
from litesata.common import *

from migen.actorlib.crc import CRCInserter, CRCChecker

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
			d = OrderedDict()
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
class LiteSATACRC(Module):
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
	check = 0x00000000
	def __init__(self, dw=32):
		self.d = Signal(self.width)
		self.value = Signal(self.width)
		self.error = Signal()

		###

		engine = CRCEngine(self.width, self.polynom)
		self.submodules += engine
		reg_i = Signal(self.width, reset=self.init)
		self.sync += reg_i.eq(engine.next)
		self.comb += [
			engine.d.eq(self.d),
			engine.last.eq(reg_i),

			self.value.eq(reg_i),
			self.error.eq(engine.next != self.check)
		]

class LiteSATACRCInserter(CRCInserter):
	def __init__(self, description):
		CRCInserter.__init__(self, LiteSATACRC, description)

class LiteSATACRCChecker(CRCChecker):
	def __init__(self, description):
		CRCChecker.__init__(self, LiteSATACRC, description)
