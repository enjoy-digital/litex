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
		raise NotImplementedError("Attempted to use a differential input, but platform does not support them")

class DifferentialOutput(Special):
	def __init__(self, i, o_p, o_n):
		Special.__init__(self)
		self.i = i
		self.o_p = o_p
		self.o_n = o_n

	def iter_expressions(self):
		yield self, "i", SPECIAL_INPUT
		yield self, "o_p", SPECIAL_OUTPUT
		yield self, "o_n", SPECIAL_OUTPUT

	@staticmethod
	def lower(dr):
		raise NotImplementedError("Attempted to use a differential output, but platform does not support them")

class CRG(Module):
	def __init__(self, clk, rst=0):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_por = ClockDomain(reset_less=True)

		if hasattr(clk, "p"):
			clk_se = Signal()
			self.specials += DifferentialInput(clk.p, clk.n, clk_se)
			clk = clk_se

		# Power on Reset (vendor agnostic)
		rst_n = Signal()
		self.sync.por += rst_n.eq(1 & ~rst)
		self.comb += [
			self.cd_sys.clk.eq(clk),
			self.cd_por.clk.eq(clk),
			self.cd_sys.rst.eq(~rst_n)
		]

class DDRInput(Special):
	def __init__(self, i, o1, o2, clk=ClockSignal()):
		Special.__init__(self)
		self.i = i
		self.o1 = o1
		self.o2 = o2
		self.clk = clk

	def iter_expressions(self):
		yield self, "i", SPECIAL_INPUT
		yield self, "o1", SPECIAL_OUTPUT
		yield self, "o2", SPECIAL_OUTPUT
		yield self, "clk", SPECIAL_INPUT

	@staticmethod
	def lower(dr):
		raise NotImplementedError("Attempted to use a DDR input, but platform does not support them")

class DDROutput(Special):
	def __init__(self, i1, i2, o, clk=ClockSignal()):
		Special.__init__(self)
		self.i1 = i1
		self.i2 = i2
		self.o = o
		self.clk = clk

	def iter_expressions(self):
		yield self, "i1", SPECIAL_INPUT
		yield self, "i2", SPECIAL_INPUT
		yield self, "o", SPECIAL_OUTPUT
		yield self, "clk", SPECIAL_INPUT

	@staticmethod
	def lower(dr):
		raise NotImplementedError("Attempted to use a DDR output, but platform does not support them")

