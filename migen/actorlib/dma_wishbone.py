from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bus import wishbone
from migen.flow.actor import *

class Reader(Module):
	def __init__(self):
		self.bus = wishbone.Interface()
		self.address = Sink([("a", 30)])
		self.data = Source([("d", 32)])
		self.busy = Signal()
	
		###
	
		bus_stb = Signal()
		data_reg_loaded = Signal()
		data_reg = Signal(32)
		
		self.comb += [
			self.busy.eq(data_reg_loaded),
			self.bus.we.eq(0),
			bus_stb.eq(self.address.stb & (~data_reg_loaded | self.data.ack)),
			self.bus.cyc.eq(bus_stb),
			self.bus.stb.eq(bus_stb),
			self.bus.adr.eq(self.address.payload.a),
			self.address.ack.eq(self.bus.ack),
			self.data.stb.eq(data_reg_loaded),
			self.data.payload.d.eq(data_reg)
		]
		self.sync += [
			If(self.data.ack, data_reg_loaded.eq(0)),
			If(self.bus.ack,
				data_reg_loaded.eq(1),
				data_reg.eq(self.bus.dat_r)
			)
		]

class Writer(Module):
	def __init__(self):
		self.bus = wishbone.Interface()
		self.address_data = Sink([("a", 30), ("d", 32)])
		self.busy = Signal()

		###

		self.comb += [
			self.busy.eq(0),
			self.bus.we.eq(1),
			self.bus.cyc.eq(self.address_data.stb),
			self.bus.stb.eq(self.address_data.stb),
			self.bus.adr.eq(self.address_data.payload.a),
			self.bus.sel.eq(0xf),
			self.bus.dat_w.eq(self.address_data.payload.d),
			self.address_data.ack.eq(self.bus.ack)
		]
