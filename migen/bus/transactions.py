from migen.fhdl.std import *

class Transaction:
	def __init__(self, address, data=0, sel=None, busname=None):
		self.address = address
		self.data = data
		if sel is None:
			bytes = (bits_for(data) + 7)//8
			sel = 2**bytes - 1
		self.sel = sel
		self.busname = busname
		self.latency = 0

	def __str__(self):
		return "<" + self.__class__.__name__ + " adr:" + hex(self.address) + " dat:" + hex(self.data) + ">"

class TRead(Transaction):
	pass

class TWrite(Transaction):
	pass
