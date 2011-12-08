from migen.fhdl import structure as f
from .simple import Simple

_desc = [
	(True,	"a",	16),
	(True,	"we",	1),
	(True,	"d",	32),
	(False,	"d",	32)
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
	
	def GetFragment(self):
		a = f.Assign
		comb = []
		rb = f.Constant(0, f.BV(32))
		for slave in self.slaves:
			comb.append(a(slave.a_i, self.master.a_o))
			comb.append(a(slave.we_i, self.master.we_o))
			comb.append(a(slave.d_i, self.master.d_o))
			rb = rb | slave.d_o
		comb.append(a(master.d_i, rb))
		return f.Fragment(comb)
