from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.bus import wishbone

class UnifiedIOObject(Actor):
	def __init__(self, dataflow=None, buses={}):
		if dataflow is not None:
			super().__init__(*dataflow)
		self.buses = buses
