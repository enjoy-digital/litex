from migen.fhdl.std import *
from migen.flow.actor import *
from migen.genlib.fifo import SyncFIFO

class Reader(Module):
	def __init__(self, lasmim, fifo_depth=None):
		self.address = Sink([("a", lasmim.aw)])
		self.data = Source([("d", lasmim.dw)])
		self.busy = Signal()
	
		###

		if fifo_depth is None:
			fifo_depth = lasmim.read_latency + 2
		assert(fifo_depth >= lasmim.read_latency)
	
		# request issuance
		request_enable = Signal()
		request_issued = Signal()

		self.comb += [
			self.bus.we.eq(0),
			lasmim.stb.eq(self.address.stb & request_enable),
			lasmim.adr.eq(self.address.payload.a),
			self.address.ack.eq(lasmim.ack),
			request_issued.eq(lasmim.stb & lasmim.ack)
		]

		# FIFO reservation level counter
		# incremented when data is planned to be queued
		# decremented when data is dequeued
		data_dequeued = Signal()
		rsv_level = Signal(max=fifo_depth+1)
		self.sync += [
			If(request_issued,
				If(~data_dequeued, rsv_level.eq(rsv_level + 1))
			).Elif(data_dequeued,
				rsv_level.eq(rsv_level - 1)
			)
		]
		self.comb += [
			self.busy.eq(rsv_level != 0),
			request_enable.eq(rsv_level != fifo_depth)
		]

		# data available
		data_available = request_issued
		for i in range(lasmim.read_latency):
			new_data_available = Signal()
			self.sync += new_data_available.eq(data_available)
			data_available = new_data_available

		# FIFO
		fifo = SyncFIFO(lasmim.dw, fifo_depth)
		self.submodules += fifo

		self.comb += [
			fifo.din.eq(lasmim.dat_r),
			fifo.we.eq(data_available),

			self.data.stb.eq(fifo.readable),
			fifo.re.eq(self.data.ack),
			self.data.payload.d.eq(fifo.dout),
			data_dequeued.eq(self.data.stb & self.data.ack)
		]


class Writer(Module):
	def __init__(self, lasmim):
		self.address_data = Sink([("a", lasmim.aw), ("d", lasmim.dw)])
		self.busy = Signal()

		###

		self.comb += [
			lasmim.we.eq(1),
			lasmim.stb.eq(self.address_data.stb),
			lasmim.adr.eq(self.address_data.payload.a),
			self.address_data.ack.eq(lasmim.ack)
		]

		busy_expr = 0
		data_valid = Signal()
		data = Signal(lasmim.dw)
		self.comb += [
			data_valid.eq(lasmim.stb & lasmim.ack),
			data.eq(self.address_data.payload.d)
		]

		for i in range(lasmim.write_latency):
			new_data_valid = Signal()
			new_data = Signal(lasmim.dw)
			self.sync += [
				new_data_valid.eq(data_valid),
				new_data.eq(data)
			]
			busy_expr = busy_expr | new_data_valid
			data_valid = new_data_valid
			data = new_data

		self.comb += [
			If(data_valid,
				lasmim.dat_we.eq(2**(lasmim.dw//8)-1),
				lasmim.dat_w.eq(data)
			),
			self.busy.eq(busy_expr)
		]
