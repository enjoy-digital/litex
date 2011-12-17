from migen.fhdl.structure import *
from migen.bus.simple import Simple

_desc = [
	(True,	"a",	14),
	(True,	"we",	1),
	(True,	"d",	8),
	(False,	"d",	8)
]

class Master(Simple):
	def __init__(self, name=""):
		Simple.__init__(self, _desc, False, name)

class Slave(Simple):
	def __init__(self, name=""):
		Simple.__init__(self, _desc, True, name)

class Interconnect:
	def __init__(self, master, slaves):
		self.master = master
		self.slaves = slaves
	
	def get_fragment(self):
		comb = []
		rb = Constant(0, BV(8))
		for slave in self.slaves:
			comb.append(slave.a_i.eq(self.master.a_o))
			comb.append(slave.we_i.eq(self.master.we_o))
			comb.append(slave.d_i.eq(self.master.d_o))
			rb = rb | slave.d_o
		comb.append(self.master.d_i.eq(rb))
		return Fragment(comb)
