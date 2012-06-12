from migen.fhdl.structure import *
from migen.flow.actor import *

class SequentialReader(Actor):
	def __init__(self, port):
		self.port = port
		assert(len(self.port.slots) == 1)
		super().__init__(
			("address", Sink, [("a", BV(self.port.hub.aw))]),
			("data", Source, [("d", BV(self.port.hub.dw))]))
	
	def get_fragment(self):
		sample = Signal()
		data_reg_loaded = Signal()
		data_reg = Signal(BV(self.port.hub.dw))
		
		accept_new = Signal()
		
		# We check that len(self.port.slots) == 1
		# and therefore we can assume that self.port.ack
		# goes low until the data phase.
		
		comb = [
			self.busy.eq(~data_reg_loaded | ~self.port.ack),
			self.port.adr.eq(self.token("address").a),
			self.port.we.eq(0),
			accept_new.eq(~data_reg_loaded | self.endpoints["data"].ack),
			self.port.stb.eq(self.endpoints["address"].stb & accept_new),
			self.endpoints["address"].ack.eq(self.port.ack & accept_new),
			self.endpoints["data"].stb.eq(data_reg_loaded),
			self.token("data").d.eq(data_reg)
		]
		sync = [
			If(self.endpoints["data"].ack,
				data_reg_loaded.eq(0)
			),
			If(sample,
				data_reg_loaded.eq(1),
				data_reg.eq(self.port.dat_r)
			),
			sample.eq(self.port.get_call_expression())
		]
		
		return Fragment(comb, sync)
