from migen.fhdl.structure import *
from migen.bus import wishbone
from migen.flow.actor import *

class Reader(Actor):
	def __init__(self):
		self.bus = wishbone.Interface()
		super().__init__(
			("address", Sink, [("a", BV(30))]),
			("data", Source, [("d", BV(32))]))
	
	def get_fragment(self):
		bus_stb = Signal()
		
		data_reg_loaded = Signal()
		data_reg = Signal(BV(32))
		
		comb = [
			self.busy.eq(data_reg_loaded),
			self.bus.we.eq(0),
			bus_stb.eq(self.endpoints["address"].stb & (~data_reg_loaded | self.endpoints["data"].ack)),
			self.bus.cyc.eq(bus_stb),
			self.bus.stb.eq(bus_stb),
			self.bus.adr.eq(self.token("address").a),
			self.endpoints["address"].ack.eq(self.bus.ack),
			self.endpoints["data"].stb.eq(data_reg_loaded),
			self.token("data").d.eq(data_reg)
		]
		sync = [
			If(self.endpoints["data"].ack,
				data_reg_loaded.eq(0)
			),
			If(self.bus.ack,
				data_reg_loaded.eq(1),
				data_reg.eq(self.bus.dat_r)
			)
		]

		return Fragment(comb, sync)

class Writer(Actor):
	def __init__(self):
		self.bus = wishbone.Interface()
		super().__init__(
			("address_data", Sink, [("a", BV(30)), ("d", BV(32))]))

	def get_fragment(self):
		comb = [
			self.busy.eq(0),
			self.bus.we.eq(1),
			self.bus.cyc.eq(self.endpoints["address_data"].stb),
			self.bus.stb.eq(self.endpoints["address_data"].stb),
			self.bus.adr.eq(self.token("address_data").a),
			self.bus.sel.eq(0xf),
			self.bus.dat_w.eq(self.token("address_data").d),
			self.endpoints["address_data"].ack.eq(self.bus.ack)
		]
		return Fragment(comb)
