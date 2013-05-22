from migen.fhdl.std import *
from migen.bus.asmibus import *
from migen.genlib.roundrobin import *
from migen.genlib.fsm import FSM
from migen.genlib.misc import optree

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

class _Selector(Module):
	def __init__(self, slicer, bankn, slots):
		nslots = len(slots)
		self.stb = Signal()
		self.ack = Signal()
		self.tag = Signal(max=nslots)
		self.adr = Signal(slots[0].adr.nbits)
		self.we = Signal()
		
		# derived classes should drive rr.request
		self.submodules.rr = RoundRobin(nslots, SP_CE)
	
		###

		# Multiplex
		rr = self.rr
		state = Signal(2)
		self.comb += [
			state.eq(Array(slot.state for slot in slots)[rr.grant]),
			self.adr.eq(Array(slot.adr for slot in slots)[rr.grant]),
			self.we.eq(Array(slot.we for slot in slots)[rr.grant]),
			self.stb.eq(
				(slicer.bank(self.adr) == bankn) \
				& (state == SLOT_PENDING)),
			rr.ce.eq(self.ack | ~self.stb),
			self.tag.eq(rr.grant)
		]
		self.comb += [If((rr.grant == i) & self.stb & self.ack, slot.process.eq(1))
			for i, slot in enumerate(slots)]

		self.complete_selector(slicer, bankn, slots)

class _SimpleSelector(_Selector):
	def complete_selector(self, slicer, bankn, slots):
		for i, slot in enumerate(slots):
			self.comb += self.rr.request[i].eq(
				(slicer.bank(slot.adr) == bankn) & \
				(slot.state == SLOT_PENDING))

class _FullSelector(_Selector):
	def complete_selector(self, slicer, bankn, slots):
		rr = self.rr

		# List outstanding requests for our bank
		outstandings = []
		for slot in slots:
			outstanding = Signal()
			self.comb += outstanding.eq(
				(slicer.bank(slot.adr) == bankn) & \
				(slot.state == SLOT_PENDING))
			outstandings.append(outstanding)
		
		# Row tracking
		openrow_r = Signal(slicer.geom_settings.row_a)
		openrow_n = Signal(slicer.geom_settings.row_a)
		openrow = Signal(slicer.geom_settings.row_a)
		self.comb += [
			openrow_n.eq(slicer.row(self.adr)),
			If(self.stb,
				openrow.eq(openrow_n)
			).Else(
				openrow.eq(openrow_r)
			)
		]
		self.sync += If(self.stb & self.ack, openrow_r.eq(openrow_n))
		hits = []
		for slot, os in zip(slots, outstandings):
			hit = Signal()
			self.comb += hit.eq((slicer.row(slot.adr) == openrow) & os)
			hits.append(hit)
		
		# Determine best request
		rr = RoundRobin(self.nslots, SP_CE)
		has_hit = Signal()
		self.comb += has_hit.eq(optree("|", hits))
		
		best_hit = [rr.request[i].eq(hit)
			for i, hit in enumerate(hits)]
		best_fallback = [rr.request[i].eq(os)
			for i, os in enumerate(outstandings)]
		select_stmt = If(has_hit,
				*best_hit
			).Else(
				*best_fallback
			)
		
		if slots[0].time:
			# Implement anti-starvation timer
			matures = []
			for slot, os in zip(slots, outstandings):
				mature = Signal()
				comb.append(mature.eq(slot.mature & os))
				matures.append(mature)
			has_mature = Signal()
			self.comb += has_mature.eq(optree("|", matures))
			best_mature = [rr.request[i].eq(mature)
				for i, mature in enumerate(matures)]
			select_stmt = If(has_mature, *best_mature).Else(select_stmt)
		self.comb += select_stmt

class _Buffer(Module):
	def __init__(self, source):
		self.stb = Signal()
		self.ack = Signal()
		self.tag = Signal(source.tag.bv)
		self.adr = Signal(source.adr.bv)
		self.we = Signal()
	
		###

		en = Signal()
		self.comb += [
			en.eq(self.ack | ~self.stb),
			source.ack.eq(en)
		]
		self.sync += [
			If(en,
				self.stb.eq(source.stb),
				self.tag.eq(source.tag),
				self.adr.eq(source.adr),
				self.we.eq(source.we)
			)
		]
	
class BankMachine(Module):
	def __init__(self, geom_settings, timing_settings, address_align, bankn, slots, full_selector):
		self.refresh_req = Signal()
		self.refresh_gnt = Signal()
		self.cmd = CommandRequestRW(geom_settings.mux_a, geom_settings.bank_a,
			bits_for(len(slots)-1))

		###

		# Sub components
		slicer = _AddressSlicer(geom_settings, address_align)
		if full_selector:
			selector = _FullSelector(slicer, bankn, slots)
			self.submodules.buf = _Buffer(selector)
			cmdsource = self.buf
		else:
			selector = _SimpleSelector(slicer, bankn, slots)
			cmdsource = selector
		self.submodules += selector
		
		# Row tracking
		has_openrow = Signal()
		openrow = Signal(geom_settings.row_a)
		hit = Signal()
		self.comb += hit.eq(openrow == slicer.row(cmdsource.adr))
		track_open = Signal()
		track_close = Signal()
		self.sync += [
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
		self.comb += [
			self.cmd.ba.eq(bankn),
			If(s_row_adr,
				self.cmd.a.eq(slicer.row(cmdsource.adr))
			).Else(
				self.cmd.a.eq(slicer.col(cmdsource.adr))
			)
		]
		
		self.comb += self.cmd.tag.eq(cmdsource.tag)
		
		# Respect write-to-precharge specification
		precharge_ok = Signal()
		t_unsafe_precharge = 2 + timing_settings.tWR - 1
		unsafe_precharge_count = Signal(max=t_unsafe_precharge+1)
		self.comb += precharge_ok.eq(unsafe_precharge_count == 0)
		self.sync += [
			If(self.cmd.stb & self.cmd.ack & self.cmd.is_write,
				unsafe_precharge_count.eq(t_unsafe_precharge)
			).Elif(~precharge_ok,
				unsafe_precharge_count.eq(unsafe_precharge_count-1)
			)
		]
		
		# Control and command generation FSM
		fsm = FSM("REGULAR", "PRECHARGE", "ACTIVATE", "REFRESH", delayed_enters=[
			("TRP", "ACTIVATE", timing_settings.tRP-1),
			("TRCD", "REGULAR", timing_settings.tRCD-1)
		])
		self.submodules += fsm
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
