from migen.fhdl.structure import *
from migen.corelogic.record import *
from migen.corelogic.fsm import *
from migen.bus import wishbone
from migen.flow.actor import *

class Reader(Actor):
	def __init__(self, layout):
		self.bus = wishbone.Master()
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.DYNAMIC),
			("address", Sink, [("a", BV(30))]),
			("data", Source, layout))
	
	def get_fragment(self):
		components, length = self.token("data").flatten(align=True, return_offset=True)
		nwords = (length + 31)//32
		
		# Address generator
		ag_stb = Signal()
		ag_sync = [If(ag_stb, self.bus.adr_o.eq(self.token("address").a))]
		if nwords > 1:
			ag_inc = Signal()
			ag_sync.append(If(ag_inc, self.bus.adr_o.eq(self.bus.adr_o + 1)))
		address_generator = Fragment(sync=ag_sync)
		
		# Output buffer
		ob_reg = Signal(BV(length))
		ob_stbs = Signal(BV(nwords))
		ob_sync = []
		top = length
		for w in range(nwords):
			if top >= 32:
				width = 32
				sl = self.bus.dat_i
			else:
				width = top
				sl = self.bus.dat_i[32-top:]
			ob_sync.append(If(ob_stbs[w],
				ob_reg[top-width:top].eq(sl)))
			top -= width
		ob_comb = []
		offset = 0
		for s in components:
			w = s.bv.width
			if isinstance(s, Signal):
				ob_comb.append(s.eq(ob_reg[length-offset-w:length-offset]))
			offset += w
		output_buffer = Fragment(ob_comb, ob_sync)
		
		# Controller
		fetch_states = ["FETCH{0}".format(w) for w in range(nwords)]
		states = ["IDLE"] + fetch_states + ["STROBE"]
		fsm = FSM(*states)
		self.busy.reset = Constant(1)
		fsm.act(fsm.IDLE,
			self.busy.eq(0),
			ag_stb.eq(1),
			self.endpoints["address"].ack.eq(1),
			If(self.endpoints["address"].stb, fsm.next_state(fsm.FETCH0))
		)
		for w in range(nwords):
			state = getattr(fsm, fetch_states[w])
			if w == nwords - 1:
				next_state = fsm.STROBE
			else:
				next_state = getattr(fsm, fetch_states[w+1])
			fsm.act(state,
				self.bus.cyc_o.eq(1),
				self.bus.stb_o.eq(1),
				ob_stbs[w].eq(1),
				If(self.bus.ack_i,
					fsm.next_state(next_state),
					ag_inc.eq(1) if nwords > 1 else None
				)
			)
		fsm.act(fsm.STROBE,
			self.endpoints["data"].stb.eq(1),
			If(self.endpoints["data"].ack, fsm.next_state(fsm.IDLE))
		)
		controller = fsm.get_fragment()

		return address_generator + output_buffer + controller
