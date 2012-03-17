from migen.fhdl.structure import *
from migen.bus.asmibus import *
from migen.corelogic.roundrobin import *
from migen.corelogic.fsm import FSM
from migen.corelogic.misc import multimux, optree

from milkymist.asmicon.multiplexer import *

# Row:Bank:Col address mapping
class _AddressSlicer:
	def __init__(self, geom_settings, address_align):
		self.geom_settings = geom_settings
		self.address_align = address_align
		
		self._b1 = self.geom_settings.col_a - self.address_align
		self._b2 = self._b1 + self.geom_settings.row_a
	
	def bank(self, address):
		return address[self._b2:]
	
	def row(self, address):
		return address[self._b1:self._b2]
	
	def col(self, address):
		return Cat(Constant(0, BV(self.address_align)), address[:self._b1])

class _Selector:
	def __init__(self, slicer, bankn, slots):
		self.slicer = slicer
		self.bankn = bankn
		self.slots = slots
		
		self.nslots = len(self.slots)
		self.stb = Signal()
		self.ack = Signal()
		self.tag = Signal(BV(bits_for(self.nslots-1)))
		self.adr = Signal(self.slots[0].adr.bv)
		self.we = Signal()
		
	def get_fragment(self):
		comb = []
		sync = []

		# List outstanding requests for our bank
		outstandings = []
		for slot in self.slots:
			outstanding = Signal()
			comb.append(outstanding.eq(
				self.slicer.bank(slot.adr) == self.bankn & \
				slot.state == SLOT_PENDING
			))
			outstandings.append(outstanding)
		
		# Row tracking
		openrow_r = Signal(BV(self.slicer.geom_settings.row_a))
		openrow_n = Signal(BV(self.slicer.geom_settings.row_a))
		openrow = Signal(BV(self.slicer.geom_settings.row_a))
		comb += [
			openrow_n.eq(self.slicer.row(self.adr)),
			If(self.stb,
				openrow.eq(openrow_n)
			).Else(
				openrow.eq(openrow_r)
			)
		]
		sync += [
			If(self.stb & self.ack,
				openrow_r.eq(openrow_n)
			)
		]
		hits = []
		for slot in self.slots:
			hit = Signal()
			comb.append(hit.eq(self.slicer.row(slot.adr) == openrow))
			hits.append(hit)
		
		# Determine best request
		rr = RoundRobin(self.nslots, SP_CE)
		has_hit = Signal()
		comb.append(has_hit.eq(optree("|", hits)))
		
		best_hit = [rr.request[i].eq(hit & os)
			for i, (hit, os) in enumerate(zip(hits, outstandings))]
		best_fallback = [rr.request[i].eq(os)
			for i, os in enumerate(outstandings)]
		select_stmt = If(has_hit,
				*best_hit
			).Else(
				*best_fallback
			)
		
		if self.slots[0].time:
			# Implement anti-starvation timer
			has_mature = Signal()
			comb.append(has_mature.eq(optree("|", [slot.mature for slot in self.slots])))
			best_mature = [rr.request[i].eq(slot.mature & os)
				for i, (slot, os) in enumerate(zip(self.slots, outstandings))]
			select_stmt = If(has_mature, *best_mature).Else(select_stmt)
		comb.append(select_stmt)
		
		# Multiplex
		state = Signal(BV(2))
		mux_outputs = [state, self.adr, self.we]
		mux_inputs = [[slot.state, slot.adr, slot.we]
			for slot in self.slots]
		comb += multimux(rr.grant, mux_inputs, mux_outputs)
		comb += [
			self.stb.eq(state == SLOT_PENDING),
			rr.ce.eq(self.ack),
			self.tag.eq(rr.grant)
		]
		comb += [slot.process.eq(rr.grant == i & self.ack)
			for i, slot in enumerate(self.slots)]
		
		return Fragment(comb, sync) + rr.get_fragment()

class _Buffer:
	def __init__(self, source):
		self.source = source
		
		self.stb = Signal()
		self.ack = Signal()
		self.tag = Signal(self.source.tag.bv)
		self.adr = Signal(self.source.adr.bv)
		self.we = Signal()
	
	def get_fragment(self):
		en = Signal()
		comb = [
			en.eq(self.ack | ~self.stb),
			self.source.ack.eq(en)
		]
		sync = [
			If(en,
				self.stb.eq(self.source.stb),
				self.tag.eq(self.source.tag),
				self.adr.eq(self.source.adr),
				self.we.eq(self.source.we)
			)
		]
		return Fragment(comb, sync)
	
class BankMachine:
	def __init__(self, geom_settings, timing_settings, address_align, bankn, slots):
		self.geom_settings = geom_settings
		self.timing_settings = timing_settings
		self.address_align = address_align
		self.bankn = bankn
		self.slots = slots
		
		self.refresh_req = Signal()
		self.refresh_gnt = Signal()
		self.cmd_request = CommandRequestRW(geom_settings.mux_a, geom_settings.bank_a,
			bits_for(len(slots)-1))

	def get_fragment(self):
		comb = []
		sync = []
		
		# Sub components
		slicer = _AddressSlicer(self.geom_settings, self.address_align)
		selector = _Selector(slicer, self.bankn, self.slots)
		buf = _Buffer(selector)
		
		# Row tracking
		has_openrow = Signal()
		openrow = Signal(BV(self.geom_settings.row_a))
		hit = Signal()
		comb.append(hit.eq(openrow == slicer.row(buf.adr)))
		track_open = Signal()
		track_close = Signal()
		sync += [
			If(track_open,
				has_openrow.eq(1),
				openrow.eq(slicer.row(buf.adr))
			),
			If(track_close,
				has_openrow.eq(0)
			)
		]
		
		# Address generation
		s_row_adr = Signal()
		comb += [
			self.cmd_request.ba.eq(self.bankn),
			If(s_row_adr,
				self.cmd_request.a.eq(slicer.row(buf.adr))
			).Else(
				self.cmd_request.a.eq(slicer.col(buf.adr))
			)
		]
		
		comb.append(self.cmd_request.tag.eq(buf.tag))
		
		# Control and command generation FSM
		fsm = FSM("REGULAR", "PRECHARGE", "ACTIVATE", "REFRESH", delayed_enters=[
			("TRP", "ACTIVATE", self.timing_settings.tRP-1),
			("TRCD", "REGULAR", self.timing_settings.tRCD-1)
		])
		fsm.act(fsm.REGULAR,
			If(self.refresh_req,
				fsm.next_state(fsm.REFRESH)
			).Elif(buf.stb,
				If(has_openrow,
					If(hit,
						self.cmd_request.stb.eq(1),
						buf.ack.eq(self.cmd_request.ack),
						self.cmd_request.is_read.eq(~buf.we),
						self.cmd_request.is_write.eq(buf.we),
						self.cmd_request.cas_n.eq(0),
						self.cmd_request.we_n.eq(~buf.we)
					).Else(
						fsm.next_state(fsm.PRECHARGE)
					)
				).Else(
					fsm.next_state(fsm.ACTIVATE)
				)
			)
		)
		fsm.act(fsm.PRECHARGE,
			# Notes:
			# 1. we are presenting the column address, A10 is always low
			# 2. since we always go to the ACTIVATE state, we do not need
			# to assert track_close.
			self.cmd_request.stb.eq(1),
			If(self.cmd_request.ack, fsm.next_state(fsm.TRP)),
			self.cmd_request.ras_n.eq(0),
			self.cmd_request.we_n.eq(0)
		)
		fsm.act(fsm.ACTIVATE,
			s_row_adr.eq(1),
			track_open.eq(1),
			self.cmd_request.stb.eq(1),
			If(self.cmd_request.ack, fsm.next_state(fsm.TRCD)),
			self.cmd_request.ras_n.eq(0)
		)
		fsm.act(fsm.REFRESH,
			self.refresh_gnt.eq(1),
			track_close.eq(1),
			If(~self.refresh_req, fsm.next_state(fsm.REGULAR))
		)
		
		return Fragment(comb, sync) + \
			selector.get_fragment() + \
			buf.get_fragment() + \
			fsm.get_fragment()
