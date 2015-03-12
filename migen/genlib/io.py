from migen.fhdl.std import *
from migen.fhdl.specials import Special
from migen.fhdl.tools import list_signals

class DifferentialInput(Special):
	def __init__(self, i_p, i_n, o):
		Special.__init__(self)
		self.i_p = i_p
		self.i_n = i_n
		self.o = o

	def iter_expressions(self):
		yield self, "i_p", SPECIAL_INPUT
		yield self, "i_n", SPECIAL_INPUT
		yield self, "o", SPECIAL_OUTPUT

	@staticmethod
	def lower(dr):
		raise NotImplementedError("Attempted to use a reset synchronizer, but platform does not support them")
