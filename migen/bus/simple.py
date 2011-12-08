from migen.fhdl import structure as f

# desc is a list of tuples, each made up of:
# 0) boolean: "master to slave"
# 1) string: name
# 2) int: width
class Simple():
	def __init__(self, desc, slave):
		for signal in desc:
			if signal[0] ^ slave:
				suffix = "_o"
			else:
				suffix = "_i"
			modules = self.__module__.split('.')
			busname = modules[len(modules)-1]
			signame = signal[1]+suffix
			setattr(self, signame, f.Signal(f.BV(signal[2]), busname+"_"+signame))
