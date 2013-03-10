from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *

class ASMIprobe(Module):
	def __init__(self, hub, trace_depth=16):
		slots = hub.get_slots()
		slot_count = len(slots)
		assert(trace_depth < 256)
		assert(slot_count < 256)
		
		self._slot_count = RegisterField("slot_count", 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._trace_depth = RegisterField("trace_depth", 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		self._slot_status = [RegisterField("slot_status" + str(i), 2, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
			for i in range(slot_count)]
		self._trace = [RegisterField("trace" + str(i), 8, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
			for i in range(trace_depth)]

		###
		
		self.comb += [
			self._slot_count.field.w.eq(slot_count),
			self._trace_depth.field.w.eq(trace_depth)
		]
		for slot, status in zip(slots, self._slot_status):
			self.comb += status.field.w.eq(slot.state)
		shift_tags = [self._trace[n].field.w.eq(self._trace[n+1].field.w)
			for n in range(len(self._trace) - 1)]
		shift_tags.append(self._trace[-1].field.w.eq(hub.tag_call))
		self.sync += If(hub.call, *shift_tags)

	def get_registers(self):
		return [self._slot_count, self._trace_depth] + self._slot_status + self._trace
