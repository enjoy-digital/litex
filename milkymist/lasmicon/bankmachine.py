from migen.fhdl.std import *
from migen.bus.asmibus import *
from migen.genlib.roundrobin import *
from migen.genlib.fsm import FSM
from migen.genlib.misc import optree

from milkymist.lasmicon.multiplexer import *

class _AddressSlicer:
	def __init__(self, col_a, address_align):
		self.col_a = col_a
		self.address_align = address_align
	
	def row(self, address):
		split = self.col_a - self.address_align
		if isinstance(address, int):
			return address >> split
		else:
			return address[split:]
		
	def col(self, address):
		split = self.col_a - self.address_align
		if isinstance(address, int):
			return (address & (2**split - 1)) << self.address_align
		else:
			return Cat(Replicate(0, self.address_align), address[:split])
	
class BankMachine(Module):
	def __init__(self, geom_settings, timing_settings, address_align, bankn, req):
		self.refresh_req = Signal()
		self.refresh_gnt = Signal()
		self.cmd = CommandRequestRW(geom_settings.mux_a, geom_settings.bank_a)

		###

		slicer = _AddressSlicer(geom_settings.col_a, address_align)
		
		# Row tracking
		has_openrow = Signal()
		openrow = Signal(geom_settings.row_a)
		hit = Signal()
		self.comb += hit.eq(openrow == slicer.row(req.adr))
		track_open = Signal()
		track_close = Signal()
		self.sync += [
			If(track_open,
				has_openrow.eq(1),
				openrow.eq(slicer.row(req.adr))
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
				self.cmd.a.eq(slicer.row(req.adr))
			).Else(
				self.cmd.a.eq(slicer.col(req.adr))
			)
		]
		
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
			).Elif(req.stb,
				If(has_openrow,
					If(hit,
						# NB: write-to-read specification is enforced by multiplexer
						self.cmd.stb.eq(1),
						req.ack.eq(self.cmd.ack),
						self.cmd.is_read.eq(~req.we),
						self.cmd.is_write.eq(req.we),
						self.cmd.cas_n.eq(0),
						self.cmd.we_n.eq(~req.we)
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
