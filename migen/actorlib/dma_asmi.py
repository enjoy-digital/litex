from migen.fhdl.std import *
from migen.flow.actor import *
from migen.genlib.buffers import ReorderBuffer

class SequentialReader(Module):
	def __init__(self, port):
		assert(len(port.slots) == 1)
		self.address = Sink([("a", port.hub.aw)])
		self.data = Source([("d", port.hub.dw)])
		self.busy = Signal()
	
		###

		sample = Signal()
		data_reg_loaded = Signal()
		data_reg = Signal(port.hub.dw)
		accept_new = Signal()
		
		# We check that len(port.slots) == 1
		# and therefore we can assume that port.ack
		# goes low until the data phase.
		
		self.comb += [
			self.busy.eq(~data_reg_loaded | ~port.ack),
			port.adr.eq(self.address.payload.a),
			port.we.eq(0),
			accept_new.eq(~data_reg_loaded | self.data.ack),
			port.stb.eq(self.address.stb & accept_new),
			self.address.ack.eq(port.ack & accept_new),
			self.data.stb.eq(data_reg_loaded),
			self.data.payload.d.eq(data_reg)
		]
		self.sync += [
			If(self.data.ack, data_reg_loaded.eq(0)),
			If(sample,
				data_reg_loaded.eq(1),
				data_reg.eq(port.dat_r)
			),
			sample.eq(port.get_call_expression())
		]

class OOOReader(Module):
	def __init__(self, port):
		assert(len(port.slots) > 1)
		self.address = Sink([("a", port.hub.aw)])
		self.data = Source([("d", port.hub.dw)])
		self.busy = Signal() # TODO: drive busy
	
		###

		tag_width = flen(port.tag_call)
		data_width = port.hub.dw
		depth = len(port.slots)
		rob = ReorderBuffer(tag_width, data_width, depth)
		self.submodules += rob
		
		self.comb += [
			port.adr.eq(self.address.payload.a),
			port.we.eq(0),
			port.stb.eq(self.address.stb & rob.can_issue),
			self.address.ack.eq(port.ack & rob.can_issue),
			rob.issue.eq(self.address.stb & port.ack),
			rob.tag_issue.eq(port.base + port.tag_issue),
			
			rob.data_call.eq(port.dat_r),
			
			self.data.stb.eq(rob.can_read),
			rob.read.eq(self.data.ack),
			self.data.payload.d.eq(rob.data_read)
		]
		self.sync += [
			# Data is announced one cycle in advance.
			# Register the call to synchronize it with the data signal.
			rob.call.eq(port.call),
			rob.tag_call.eq(port.tag_call)
		]

class SequentialWriter(Module):
	def __init__(self, port):
		assert(len(port.slots) == 1)
		self.address_data = Sink([("a", port.hub.aw), ("d", port.hub.dw)])
		self.busy = Signal()

		###

		data_reg = Signal(port.hub.dw)
		self.comb += [
			port.adr.eq(self.address_data.payload.a),
			port.we.eq(1),
			port.stb.eq(self.address_data.stb),
			self.address_data.ack.eq(port.ack),
			port.dat_wm.eq(0)
		]
		self.sync += [
			port.dat_w.eq(0),
			If(port.get_call_expression(),
				self.busy.eq(0),
				port.dat_w.eq(data_reg)
			),
			If(self.address_data.stb & self.address_data.ack,
				self.busy.eq(1),
				data_reg.eq(self.address_data.payload.d)
			)
		]

class _WriteSlot(Module):
	def __init__(self, port, load_data, n):
		self.busy = Signal()

		###

		drive_data = Signal()
		data_reg = Signal(port.hub.dw)
		self.comb += [
			If(drive_data, port.dat_w.eq(data_reg)),
			port.dat_wm.eq(0)
		]

		self.sync += [
			drive_data.eq(0),
			If(port.get_call_expression(n),
				self.busy.eq(0),
				drive_data.eq(1)
			),
			If(port.stb & port.ack & (port.tag_issue == n),
				self.busy.eq(1),
				data_reg.eq(load_data)
			),
		]

class OOOWriter(Module):
	def __init__(self, port):
		assert(len(port.slots) > 1)
		self.address_data = Sink([("a", port.hub.aw), ("d", port.hub.dw)])
		self.busy = Signal()

		###

		self.comb += [
			port.adr.eq(self.address_data.payload.a),
			port.we.eq(1),
			port.stb.eq(self.address_data.stb),
			self.address_data.ack.eq(port.ack)
		]

		busy = 0
		for i in range(len(port.slots)):
			write_slot = _WriteSlot(port, self.address_data.payload.d, i)
			self.submodules += write_slot
			busy = busy | write_slot.busy
		self.comb += self.busy.eq(busy)

def Reader(port):
	if len(port.slots) == 1:
		return SequentialReader(port)
	else:
		return OOOReader(port)

def Writer(port):
	if len(port.slots) == 1:
		return SequentialWriter(port)
	else:
		return OOOWriter(port)
