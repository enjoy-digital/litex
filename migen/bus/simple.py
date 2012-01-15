from migen.fhdl.structure import *

def get_sig_name(signal, slave):
	if signal[0] ^ slave:
		suffix = "_o"
	else:
		suffix = "_i"
	return signal[1] + suffix

# desc is a list of tuples, each made up of:
# 0) boolean: "master to slave"
# 1) string: name
# 2) int: width
class Simple():
	def __init__(self, desc, slave, name):
		for signal in desc:
			modules = self.__module__.split('.')
			busname = modules[len(modules)-1]
			if name:
				busname += "_" + name
			signame = get_sig_name(signal, slave)
			setattr(self, signame, Signal(BV(signal[2]), busname + "_" + signame))
	
	def signals(self):
		return [self.__dict__[k]
			for k in self.__dict__
			if isinstance(self.__dict__[k], Signal)]
