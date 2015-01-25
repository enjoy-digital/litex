from migen.fhdl.std import *
from migen.bank.description import *
from migen.genlib.fsm import FSM, NextState
from migen.flow.actor import *
from migen.actorlib.fifo import AsyncFIFO, SyncFIFO
from migen.flow.plumbing import Buffer
from migen.fhdl.specials import Memory

def data_layout(dw):
	return [("data", dw, DIR_M_TO_S)]

def hit_layout():
	return [("hit", 1, DIR_M_TO_S)]

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
