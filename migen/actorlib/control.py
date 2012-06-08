from operator import mul
from functools import reduce

from migen.fhdl.structure import *
from migen.corelogic.record import *
from migen.corelogic.fsm import *
from migen.flow.actor import *

# Generates integers from start to maximum-1
class For(Actor):
	def __init__(self, *maxima, start=False, step=False):
		self.dimensions = len(maxima)
		self.start = start
		self.step = step
		params = ["end"]
		if start: params.append("start")
		if step: params.append("step")
		self.d_bv = [BV(bits_for(dimension)) for dimension in maxima]
		l_sink = [("d{0}".format(n), [(p, bv) for p in params])
			for n, bv in enumerate(self.d_bv)]
		l_source = [("d{0}".format(n), bv)
			for n, bv in enumerate(self.d_bv)]
		super().__init__(
			("sink", Sink, l_sink),
			("source", Source, l_source))
	
	def get_fragment(self):
		load = Signal()
		ce = Signal()
		last = Signal()
		
		counters_v = [Signal(bv, variable=True) for bv in self.d_bv]
		counters = [getattr(self.token("source"), "d{0}".format(n))
			for n in range(self.dimensions)]
		
		params = [getattr(self.token("sink"), "d{0}".format(n))
			for n in range(self.dimensions)]
		if self.start:
			starts = [p.start for p in params]
			start_rs = [Signal(s.bv, variable=True) for s in starts]
		else:
			start_rs = [Constant(0, bv) for bv in self.d_bv]
		if self.step:
			steps = [p.step for p in params]
			step_rs = [Signal(s.bv, variable=True) for s in steps]
		else:
			step_rs = [Constant(1, bv) for bv in self.d_bv]
		ends = [p.end for p in params]
		end_rs = [Signal(s.bv, variable=True) for s in ends]
		
		lasts = Signal(BV(self.dimensions))
		
		on_ce = [
			If(lasts[n],
				counter.eq(start)
			).Else(
				counter.eq(counter + step)
			)
			for n, counter, start, step
			  in zip(range(self.dimensions), counters_v, start_rs, step_rs)
		]
		lasts_gen = [
			lasts[n].eq(counter + step >= end if self.step else counter + step == end)
			for n, counter, step, end
			  in zip(range(self.dimensions), counters_v, step_rs, end_rs)
		]
		sync = [
			If(load,
				Cat(*start_rs).eq(Cat(*starts)) if self.start else None,
				Cat(*step_rs).eq(Cat(*steps)) if self.step else None,
				Cat(*end_rs).eq(Cat(*ends)),
				Cat(*counters_v).eq(Cat(*start_rs))
			),
			If(ce, *on_ce)
		] + lasts_gen + [
			Cat(*counters).eq(Cat(*counters_v))
		]
		counters_fragment = Fragment(sync=sync)
		
		fsm = FSM("IDLE", "ACTIVE")
		fsm.act(fsm.IDLE,
			load.eq(1),
			self.endpoints["sink"].ack.eq(1),
			If(self.endpoints["sink"].stb, fsm.next_state(fsm.ACTIVE))
		)
		fsm.act(fsm.ACTIVE,
			self.busy.eq(1),
			self.endpoints["source"].stb.eq(1),
			If(self.endpoints["source"].ack,
				ce.eq(1),
				If(last, fsm.next_state(fsm.IDLE))
			)
		)
		return counters_fragment + fsm.get_fragment()
