from migen.fhdl.structure import *
from migen.bank.description import *
from migen.flow.hooks import DFGHook

ISD_MAGIC = 0x6ab4

class EndpointReporter:
	def __init__(self, endpoint, nbits):
		self.endpoint = endpoint
		self.nbits = nbits
		self.reset = Signal()
		self.freeze = Signal()
		
		self._ack_count = RegisterField("ack_count", self.nbits, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._nack_count = RegisterField("nack_count", self.nbits, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._cur_stb = Field("cur_stb", 1, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._cur_ack = Field("cur_ack", 1, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._cur_status = RegisterFields("cur_status", [self._cur_stb, self._cur_ack])
	
	def get_registers(self):
		return [self._ack_count, self._nack_count, self._cur_status]
	
	def get_fragment(self):
		stb = Signal()
		ack = Signal()
		ack_count = Signal(self.nbits)
		nack_count = Signal(self.nbits)
		comb = [
			self._cur_stb.w.eq(stb),
			self._cur_ack.w.eq(ack)
		]
		sync = [
			# register monitored signals
			stb.eq(self.endpoint.stb),
			ack.eq(self.endpoint.ack),
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
				self._ack_count.field.w.eq(ack_count),
				self._nack_count.field.w.eq(nack_count)
			)
		]
		return Fragment(comb, sync)

class DFGReporter(DFGHook):
	def __init__(self, dfg, nbits):
		self._nbits = nbits
		
		self._r_magic = RegisterField("magic", 16, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._r_neps = RegisterField("neps", 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._r_nbits = RegisterField("nbits", 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._r_freeze = RegisterField("freeze", 1)
		self._r_reset = RegisterRaw("reset", 1)
		
		self.order = []
		DFGHook.__init__(self, dfg, self._create)
	
	def _create(self, u, ep, v):
		self.order.append((u, ep, v))
		return EndpointReporter(u.actor.endpoints[ep], self._nbits)
	
	def print_map(self):
		for n, (u, ep, v) in enumerate(self.order):
			print("#" + str(n) + ": " + str(u) + ":" + ep + "  ->  " + str(v))
	
	def get_registers(self):
		registers = [self._r_magic, self._r_neps, self._r_nbits,
			self._r_freeze, self._r_reset]
		for u, ep, v in self.order:
			registers += self.nodepair_to_ep[(u, v)][ep].get_registers()
		return registers
	
	def get_fragment(self):
		comb = [
			self._r_magic.field.w.eq(ISD_MAGIC),
			self._r_neps.field.w.eq(len(self.order)),
			self._r_nbits.field.w.eq(self._nbits)
		]
		for h in self.hooks_iter():
			comb += [
				h.freeze.eq(self._r_freeze.field.r),
				h.reset.eq(self._r_reset.re)
			]
		return Fragment(comb) + DFGHook.get_fragment(self)
