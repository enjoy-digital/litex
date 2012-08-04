from migen.fhdl.structure import *
from migen.bank.description import *
from migen.bank import csrgen

class ASMIprobe:
	def __init__(self, address, hub, trace_depth=16):
		self.hub = hub
		self.trace_depth = trace_depth
		
		slot_count = len(self.hub.get_slots())
		assert(self.trace_depth < 256)
		assert(slot_count < 256)
		
		self._slot_count = RegisterField("slot_count", 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._trace_depth = RegisterField("trace_depth", 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._slot_status = [RegisterField("slot_status", 2, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
			for i in range(slot_count)]
		self._trace = [RegisterField("trace", 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
			for i in range(self.trace_depth)]

		self.bank = csrgen.Bank([self._slot_count, self._trace_depth]
			+ self._slot_status + self._trace, address=address)
	
	def get_fragment(self):
		slots = self.hub.get_slots()
		comb = [
			self._slot_count.field.w.eq(len(slots)),
			self._trace_depth.field.w.eq(self.trace_depth)
		]
		for slot, status in zip(slots, self._slot_status):
			comb.append(status.field.w.eq(slot.state))
		shift_tags = [self._trace[n].field.w.eq(self._trace[n+1].field.w)
			for n in range(len(self._trace) - 1)]
		shift_tags.append(self._trace[-1].field.w.eq(self.hub.tag_call))
		sync = [If(self.hub.call, *shift_tags)]
		return Fragment(comb, sync) + self.bank.get_fragment()
