# Simple Processor Interface

from migen.fhdl.structure import *
from migen.bank.description import *
from migen.flow.actor import *

class Collector(Actor):
	def __init__(self, layout, depth=1024):
		super().__init__(("sink", Sink, layout))
		self._depth = depth
		self._dw = sum(len(s) for s in self.token("sink").flatten())
		
		# TODO: reg_wc should have atomic update
		self._reg_wa = RegisterField("write_address", bits_for(self._depth-1), access_bus=READ_WRITE, access_dev=READ_WRITE)
		self._reg_wc = RegisterField("write_count", bits_for(self._depth), access_bus=READ_WRITE, access_dev=READ_WRITE)
		self._reg_ra = RegisterField("read_address", bits_for(self._depth-1), access_bus=READ_WRITE, access_dev=READ_ONLY)
		self._reg_rd = RegisterField("read_data", self._dw, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
	
	def get_registers(self):
		return [self._reg_wa, self._reg_wc, self._reg_ra, self._reg_rd]
	
	def get_fragment(self):
		wa = Signal(BV(bits_for(self._depth-1)))
		dummy = Signal(BV(self._dw))
		wd = Signal(BV(self._dw))
		we = Signal()
		wp = MemoryPort(wa, dummy, wd, we)
		ra = Signal(BV(bits_for(self._depth-1)))
		rd = Signal(BV(self._dw))
		rp = MemoryPort(ra, rd)
		mem = Memory(self._dw, self._depth, wp, rp)
		
		comb = [
			If(self._reg_wc.field.r != 0,
				self.endpoints["sink"].ack.eq(1),
				If(self.endpoints["sink"].stb,
					self._reg_wa.field.we.eq(1),
					self._reg_wc.field.we.eq(1),
					we.eq(1)
				)
			),
			self._reg_wa.field.w.eq(self._reg_wa.field.r + 1),
			self._reg_wc.field.w.eq(self._reg_wc.field.r - 1),
			
			wa.eq(self._reg_wa.field.r),
			wd.eq(Cat(*self.token("sink").flatten())),
			
			ra.eq(self._reg_ra.field.r),
			self._reg_rd.field.w.eq(rd)
		]
		
		return Fragment(comb, memories=[mem])
