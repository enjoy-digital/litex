from migen.fhdl.structure import *
from migen.corelogic.misc import optree
from migen.bus.simple import Simple

_desc = [
	(True,	"adr",	14),
	(True,	"we",	1),
	(True,	"dat",	8),
	(False,	"dat",	8)
]

class Master(Simple):
	def __init__(self):
		Simple.__init__(self, _desc, False)

class Slave(Simple):
	def __init__(self):
		Simple.__init__(self, _desc, True)

class Interconnect:
	def __init__(self, master, slaves):
		self.master = master
		self.slaves = slaves
	
	def get_fragment(self):
		comb = []
		for slave in self.slaves:
			comb.append(slave.adr_i.eq(self.master.adr_o))
			comb.append(slave.we_i.eq(self.master.we_o))
			comb.append(slave.dat_i.eq(self.master.dat_o))
		rb = optree("|", [slave.dat_o for slave in self.slaves])
		comb.append(self.master.dat_i.eq(rb))
		return Fragment(comb)
