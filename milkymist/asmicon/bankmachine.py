from migen.fhdl.structure import *
from migen.bus.asmibus import *
from migen.corelogic.roundrobin import *
from migen.corelogic.fsm import FSM
from migen.corelogic.misc import optree

from milkymist.asmicon.multiplexer import *

# Row:Bank:Col address mapping
class _AddressSlicer:
	def __init__(self, geom_settings, address_align):
		self.geom_settings = geom_settings
		self.address_align = address_align
		
		self._b1 = self.geom_settings.col_a - self.address_align
		self._b2 = self._b1 + self.geom_settings.bank_a
	
	def row(self, address):
		if isinstance(address, int):
			return address >> self._b2
		else:
			return address[self._b2:]
	
	def bank(self, address):
		if isinstance(address, int):
			return (address & (2**self._b2 - 1)) >> self._b1
		else:
			return address[self._b1:self._b2]
	
	def col(self, address):
		if isinstance(address, int):
			return (address & (2**self._b1 - 1)) << self.address_align
		else:
			return Cat(Replicate(0, self.address_align), address[:self._b1])

class _Selector:
	def __init__(self, slicer, bankn, slots):
		self.slicer = slicer
		self.bankn = bankn
		self.slots = slots
		
		self.nslots = len(self.slots)
		self.stb = Signal()
		self.ack = Signal()
		self.tag = Signal(bits_for(self.nslots-1))
		self.adr = Signal(self.slots[0].adr.nbits)
		self.we = Signal()
		
		# derived classes should drive rr.request
		self.rr = RoundRobin(self.nslots, SP_CE)
	
	def get_fragment(self):
		comb = []
		rr = self.rr
		
		# Multiplex
		state = Signal(2)
		comb += [
			state.eq(Array(slot.state for slot in self.slots)[rr.grant]),
			self.adr.eq(Array(slot.adr for slot in self.slots)[rr.grant]),
			self.we.eq(Array(slot.we for slot in self.slots)[rr.grant]),
			self.stb.eq(
				(self.slicer.bank(self.adr) == self.bankn) \
				& (state == SLOT_PENDING)),
			rr.ce.eq(self.ack | ~self.stb),
			self.tag.eq(rr.grant)
		]
		comb += [If((rr.grant == i) & self.stb & self.ack, slot.process.eq(1))
			for i, slot in enumerate(self.slots)]
			
		return Fragment(comb) + rr.get_fragment()

class _SimpleSelector(_Selector):
	def get_fragment(self):
		comb = []
		for i, slot in enumerate(self.slots):
			comb.append(self.rr.request[i].eq(
				(self.slicer.bank(slot.adr) == self.bankn) & \
				(slot.state == SLOT_PENDING)
			))
	
		return Fragment(comb) + super().get_fragment()

class _FullSelector(_Selector):
	def get_fragment(self):
		comb = []
		sync = []
		rr = self.rr

		# List outstanding requests for our bank
		outstandings = []
		for slot in self.slots:
			outstanding = Signal()
			comb.append(outstanding.eq(
				(self.slicer.bank(slot.adr) == self.bankn) & \
				(slot.state == SLOT_PENDING)
			))
			outstandings.append(outstanding)
		
		# Row tracking
		openrow_r = Signal(self.slicer.geom_settings.row_a)
		openrow_n = Signal(self.slicer.geom_settings.row_a)
		openrow = Signal(self.slicer.geom_settings.row_a)
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
		for slot, os in zip(self.slots, outstandings):
			hit = Signal()
			comb.append(hit.eq((self.slicer.row(slot.adr) == openrow) & os))
			hits.append(hit)
		
		# Determine best request
		rr = RoundRobin(self.nslots, SP_CE)
		has_hit = Signal()
		comb.append(has_hit.eq(optree("|", hits)))
		
		best_hit = [rr.request[i].eq(hit)
			for i, hit in enumerate(hits)]
		best_fallback = [rr.request[i].eq(os)
			for i, os in enumerate(outstandings)]
		select_stmt = If(has_hit,
				*best_hit
			).Else(
				*best_fallback
			)
		
		if self.slots[0].time:
			# Implement anti-starvation timer
			matures = []
			for slot, os in zip(self.slots, outstandings):
				mature = Signal()
				comb.append(mature.eq(slot.mature & os))
				matures.append(mature)
			has_mature = Signal()
			comb.append(has_mature.eq(optree("|", matures)))
			best_mature = [rr.request[i].eq(mature)
				for i, mature in enumerate(matures)]
			select_stmt = If(has_mature, *best_mature).Else(select_stmt)
		comb.append(select_stmt)
		
		return Fragment(comb, sync) + super().get_fragment()

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
	def __init__(self, geom_settings, timing_settings, address_align, bankn, slots, full_selector):
		self.geom_settings = geom_settings
		self.timing_settings = timing_settings
		self.address_align = address_align
		self.bankn = bankn
		self.slots = slots
		self.full_selector = full_selector
		
		self.refresh_req = Signal()
		self.refresh_gnt = Signal()
		self.cmd = CommandRequestRW(geom_settings.mux_a, geom_settings.bank_a,
			bits_for(len(slots)-1))

	def get_fragment(self):
		comb = []
		sync = []
		
		# Sub components
		slicer = _AddressSlicer(self.geom_settings, self.address_align)
		if self.full_selector:
			selector = _FullSelector(slicer, self.bankn, self.slots)
			buf = _Buffer(selector)
			cmdsource = buf
		else:
			selector = _SimpleSelector(slicer, self.bankn, self.slots)
			cmdsource = selector
		
		# Row tracking
		has_openrow = Signal()
		openrow = Signal(self.geom_settings.row_a)
		hit = Signal()
		comb.append(hit.eq(openrow == slicer.row(cmdsource.adr)))
		track_open = Signal()
		track_close = Signal()
		sync += [
			If(track_open,
				has_openrow.eq(1),
				openrow.eq(slicer.row(cmdsource.adr))
			),
			If(track_close,
				has_openrow.eq(0)
			)
		]
		
		# Address generation
		s_row_adr = Signal()
		comb += [
			self.cmd.ba.eq(self.bankn),
			If(s_row_adr,
				self.cmd.a.eq(slicer.row(cmdsource.adr))
			).Else(
				self.cmd.a.eq(slicer.col(cmdsource.adr))
			)
		]
		
		comb.append(self.cmd.tag.eq(cmdsource.tag))
		
		# Respect write-to-precharge specification
		precharge_ok = Signal()
		t_unsafe_precharge = 2 + self.timing_settings.tWR - 1
		unsafe_precharge_count = Signal(bits_for(t_unsafe_precharge))
		comb.append(precharge_ok.eq(unsafe_precharge_count == 0))
		sync += [
			If(self.cmd.stb & self.cmd.ack & self.cmd.is_write,
				unsafe_precharge_count.eq(t_unsafe_precharge)
			).Elif(~precharge_ok,
				unsafe_precharge_count.eq(unsafe_precharge_count-1)
			)
		]
		
		# Control and command generation FSM
		fsm = FSM("REGULAR", "PRECHARGE", "ACTIVATE", "REFRESH", delayed_enters=[
			("TRP", "ACTIVATE", self.timing_settings.tRP-1),
			("TRCD", "REGULAR", self.timing_settings.tRCD-1)
		])
		fsm.act(fsm.REGULAR,
			If(self.refresh_req,
				fsm.next_state(fsm.REFRESH)
			).Elif(cmdsource.stb,
				If(has_openrow,
					If(hit,
						# NB: write-to-read specification is enforced by multiplexer
						self.cmd.stb.eq(1),
						cmdsource.ack.eq(self.cmd.ack),
						self.cmd.is_read.eq(~cmdsource.we),
						self.cmd.is_write.eq(cmdsource.we),
						self.cmd.cas_n.eq(0),
						self.cmd.we_n.eq(~cmdsource.we)
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
			If(precharge_ok,
				self.cmd.stb.eq(1),
				If(self.cmd.ack, fsm.next_state(fsm.TRP)),
				self.cmd.ras_n.eq(0),
				self.cmd.we_n.eq(0)
			)
		)
		fsm.act(fsm.ACTIVATE,
			s_row_adr.eq(1),
			track_open.eq(1),
			self.cmd.stb.eq(1),
			If(self.cmd.ack, fsm.next_state(fsm.TRCD)),
			self.cmd.ras_n.eq(0)
		)
		fsm.act(fsm.REFRESH,
			self.refresh_gnt.eq(precharge_ok),
			track_close.eq(1),
			If(~self.refresh_req, fsm.next_state(fsm.REGULAR))
		)
		
		if self.full_selector:
			buf_fragment = buf.get_fragment()
		else:
			buf_fragment = Fragment()
		return Fragment(comb, sync) + \
			selector.get_fragment() + \
			buf_fragment + \
			fsm.get_fragment()
