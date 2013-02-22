from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.genlib.buffers import ReorderBuffer

class SequentialReader(Actor):
	def __init__(self, port):
		self.port = port
		assert(len(self.port.slots) == 1)
		Actor.__init__(self,
			("address", Sink, [("a", self.port.hub.aw)]),
			("data", Source, [("d", self.port.hub.dw)]))
	
	def get_fragment(self):
		sample = Signal()
		data_reg_loaded = Signal()
		data_reg = Signal(self.port.hub.dw)
		
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

class OOOReader(Actor):
	def __init__(self, port):
		self.port = port
		assert(len(self.port.slots) > 1)
		Actor.__init__(self,
			("address", Sink, [("a", self.port.hub.aw)]),
			("data", Source, [("d", self.port.hub.dw)]))
	
	def get_fragment(self):
		tag_width = len(self.port.tag_call)
		data_width = self.port.hub.dw
		depth = len(self.port.slots)
		rob = ReorderBuffer(tag_width, data_width, depth)
		
		comb = [
			self.port.adr.eq(self.token("address").a),
			self.port.we.eq(0),
			self.port.stb.eq(self.endpoints["address"].stb & rob.can_issue),
			self.endpoints["address"].ack.eq(self.port.ack & rob.can_issue),
			rob.issue.eq(self.endpoints["address"].stb & self.port.ack),
			rob.tag_issue.eq(self.port.base + self.port.tag_issue),
			
			rob.data_call.eq(self.port.dat_r),
			
			self.endpoints["data"].stb.eq(rob.can_read),
			rob.read.eq(self.endpoints["data"].ack),
			self.token("data").d.eq(rob.data_read)
		]
		sync = [
			# Data is announced one cycle in advance.
			# Register the call to synchronize it with the data signal.
			rob.call.eq(self.port.call),
			rob.tag_call.eq(self.port.tag_call)
		]
		
		return Fragment(comb, sync) + rob.get_fragment()

class Reader:
	def __init__(self, port):
		if len(port.slots) == 1:
			self.__class__ = SequentialReader
			SequentialReader.__init__(self, port)
		else:
			self.__class__ = OOOReader
			OOOReader.__init__(self, port)
