from migen.fhdl import structure as f
from functools import partial

class Master:
	def __init__(self):
		d = partial(f.Declare, self)
		d("a_o", f.BV(16))
		d("we_o")
		d("d_o", f.BV(32))
		d("d_i", f.BV(32))

class Slave:
	def __init__(self):
		d = partial(f.Declare, self)
		d("a_i", f.BV(16))
		d("we_i")
		d("d_i", f.BV(32))
		d("d_o", f.BV(32))

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