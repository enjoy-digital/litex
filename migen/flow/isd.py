from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.flow.hooks import DFGHook

ISD_MAGIC = 0x6ab4

class EndpointReporter(Module, AutoCSR):
	def __init__(self, endpoint, nbits):
		self.reset = Signal()
		self.freeze = Signal()
		
		self._ack_count = CSRStatus(nbits)
		self._nack_count = CSRStatus(nbits)
		self._cur_status = CSRStatus(2)
	
		###

		stb = Signal()
		ack = Signal()
		self.comb += self._cur_status.status.eq(Cat(stb, ack))
		ack_count = Signal(nbits)
		nack_count = Signal(nbits)
		self.sync += [
			# register monitored signals
			stb.eq(endpoint.stb),
			ack.eq(endpoint.ack),
			# count operations
			If(self.reset,
				ack_count.eq(0),
				nack_count.eq(0)
			).Else(
				If(stb,
					If(ack,
						ack_count.eq(ack_count + 1)
					).Else(
						nack_count.eq(nack_count + 1)
					)
				)
			),
			If(~self.freeze,
				self._ack_count.status.eq(ack_count),
				self._nack_count.status.eq(nack_count)
			)
		]

class DFGReporter(DFGHook, AutoCSR):
	def __init__(self, dfg, nbits):
		self._r_magic = CSRStatus(16)
		self._r_neps = CSRStatus(8)
		self._r_nbits = CSRStatus(8)
		self._r_freeze = CSRStorage()
		self._r_reset = CSR()
		
		###

		DFGHook.__init__(self, dfg,
			lambda u, ep, v: EndpointReporter(u.endpoints[ep], nbits))

		self.comb += [
			self._r_magic.status.eq(ISD_MAGIC),
			self._r_neps.status.eq(len(self.hooks_iter())),
			self._r_nbits.status.eq(nbits)
		]
		for h in self.hooks_iter():
			self.comb += [
				h.freeze.eq(self._r_freeze.storage),
				h.reset.eq(self._r_reset.re)
			]
