from migen.fhdl.structure import *
from migen.bus.simple import *
from migen.bus.transactions import *
from migen.sim.generic import PureSimulable

data_width = 8

class Interface(SimpleInterface):
	def __init__(self):
		super().__init__(Description(
			(M_TO_S,	"adr",		14),
			(M_TO_S,	"we",		1),
			(M_TO_S,	"dat_w",	data_width),
			(S_TO_M,	"dat_r",	data_width)))

class Interconnect(SimpleInterconnect):
	pass

class Initiator(PureSimulable):
	def __init__(self, generator, bus=Interface()):
		self.generator = generator
		self.bus = bus
		self.transaction = None
		self.done = False
		
	def do_simulation(self, s):
		if not self.done:
			if self.transaction is not None:
				if isinstance(self.transaction, TRead):
					self.transaction.data = s.rd(self.bus.dat_r)
				else:
					s.wr(self.bus.we, 0)
			try:
				self.transaction = next(self.generator)
			except StopIteration:
				self.transaction = None
				self.done = True
			if self.transaction is not None:
				s.wr(self.bus.adr, self.transaction.address)
				if isinstance(self.transaction, TWrite):
					s.wr(self.bus.we, 1)
					s.wr(self.bus.dat_w, self.transaction.data)
