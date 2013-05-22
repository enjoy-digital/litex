from migen.fhdl.std import *
from migen.bank.description import *

class ASMIprobe(Module):
	def __init__(self, hub, trace_depth=16):
		slots = hub.get_slots()
		slot_count = len(slots)
		
		self._slot_count = CSRStatus(bits_for(slot_count))
		self._trace_depth = CSRStatus(bits_for(trace_depth))
		self._slot_status = [CSRStatus(2, name="slot_status" + str(i)) for i in range(slot_count)]
		self._trace = [CSRStatus(bits_for(slot_count-1), name="trace" + str(i)) for i in range(trace_depth)]

		###
		
		self.comb += [
			self._slot_count.status.eq(slot_count),
			self._trace_depth.status.eq(trace_depth)
		]
		for slot, status in zip(slots, self._slot_status):
			self.sync += status.status.eq(slot.state)
		shift_tags = [self._trace[n].status.eq(self._trace[n+1].status)
			for n in range(len(self._trace) - 1)]
		shift_tags.append(self._trace[-1].status.eq(hub.tag_call))
		self.sync += If(hub.call, *shift_tags)

	def get_csrs(self):
		return [self._slot_count, self._trace_depth] + self._slot_status + self._trace
