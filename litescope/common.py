from migen.genlib.record import *

def dat_layout(dw):
	return [
		("stb", 1, DIR_M_TO_S),
		("dat", dw, DIR_M_TO_S)
	]

def hit_layout():
	return [
		("stb", 1, DIR_M_TO_S),
		("hit", 1, DIR_M_TO_S)
	]

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class Counter(Module):
	def __init__(self, signal=None, **kwargs):
		if signal is None:
			self.value = Signal(**kwargs)
		else:
			self.value = signal
		self.width = flen(self.value)
		self.sync += self.value.eq(self.value+1)

@DecorateModule(InsertReset)
@DecorateModule(InsertCE)
class Timeout(Module):
	def __init__(self, length):
		self.reached = Signal()
		###
		value = Signal(max=length)
		self.sync += value.eq(value+1)
		self.comb += [
			self.reached.eq(value == length)
		]
