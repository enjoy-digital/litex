from migen.fhdl.structure import *
from migen.corelogic.misc import optree

(S_TO_M, M_TO_S) = range(2)

# desc is a list of tuples, each made up of:
# 0) S_TO_M/M_TO_S: data direction
# 1) string: name
# 2) int: width

class Description:
	def __init__(self, *desc):
		self.desc = desc
	
	def get_names(self, direction, *exclude_list):
		exclude = set(exclude_list)
		return [signal[1]
			for signal in self.desc
			if signal[0] == direction and signal[1] not in exclude]

class SimpleInterface:
	def __init__(self, desc):
		self.desc = desc
		modules = self.__module__.split(".")
		busname = modules[len(modules)-1]
		for signal in self.desc.desc:
			signame = signal[1]
			setattr(self, signame, Signal(BV(signal[2]), busname + "_" + signame))

def simple_interconnect_stmts(desc, master, slaves):
	s2m = desc.get_names(S_TO_M)
	m2s = desc.get_names(M_TO_S)
	sl = [getattr(slave, name).eq(getattr(master, name))
		for name in m2s for slave in slaves]
	sl += [getattr(master, name).eq(
			optree("|", [getattr(slave, name) for slave in slaves])
		)
		for name in s2m]
	return sl

class SimpleInterconnect:
	def __init__(self, master, slaves):
		self.master = master
		self.slaves = slaves
	
	def get_fragment(self):
		return Fragment(simple_interconnect_stmts(self.master.desc, self.master, self.slaves))
