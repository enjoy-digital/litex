from migen.fhdl.std import *
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.flow.actor import Sink, Source

class UART(Module, AutoCSR):
	def __init__(self, phy):
		self._rxtx = CSR(8)

		self.submodules.ev = EventManager()
		self.ev.tx = EventSourcePulse()
		self.ev.rx = EventSourcePulse()
		self.ev.finalize()
		###
		self.sync += [
			If(self._rxtx.re,
				phy.tx.sink.stb.eq(1),
				phy.tx.sink.d.eq(self._rxtx.r),
			).Elif(phy.tx.sink.ack,
				phy.tx.sink.stb.eq(0)
			),
			If(phy.rx.source.stb,
				self._rxtx.w.eq(phy.rx.source.d)
			)
		]
		self.comb += [
			self.ev.tx.trigger.eq(phy.tx.sink.stb & phy.tx.sink.ack),
			self.ev.rx.trigger.eq(phy.rx.source.stb) #phy.rx.source.ack supposed to be always 1
		]
