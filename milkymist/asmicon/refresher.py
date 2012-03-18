from migen.fhdl.structure import *
from migen.corelogic.misc import timeline
from migen.corelogic.fsm import FSM

from milkymist.asmicon.multiplexer import *

class Refresher:
	def __init__(self, a, ba, tRP, tREFI, tRFC):
		self.tRP = tRP
		self.tREFI = tREFI
		self.tRFC = tRFC
		
		self.req = Signal()
		self.ack = Signal() # 1st command 1 cycle after assertion of ack
		self.cmd = CommandRequest(a, ba)
	
	def get_fragment(self):
		comb = []
		sync = []
		
		# Refresh sequence generator:
		# PRECHARGE ALL --(tRP)--> AUTO REFRESH --(tRFC)--> done
		seq_start = Signal()
		seq_done = Signal()
		sync += [
			self.cmd.a.eq(2**10),
			self.cmd.ba.eq(0),
			self.cmd.cas_n.eq(1),
			self.cmd.ras_n.eq(1),
			self.cmd.we_n.eq(1)
		]
		sync += timeline(seq_start, [
			(1, [
				self.cmd.ras_n.eq(0),
				self.cmd.we_n.eq(0)
			]),
			(1+self.tRP, [
				self.cmd.cas_n.eq(0),
				self.cmd.ras_n.eq(0)
			]),
			(1+self.tRP+self.tRFC, [
				seq_done.eq(1)
			])
		])
		
		# Periodic refresh counter
		counter = Signal(BV(bits_for(self.tREFI - 1)))
		start = Signal()
		sync += [
			start.eq(0),
			If(counter == 0,
				start.eq(1),
				counter.eq(self.tREFI - 1)
			).Else(
				counter.eq(counter - 1)
			)
		]
		
		# Control FSM
		fsm = FSM("IDLE", "WAIT_GRANT", "WAIT_SEQ")
		fsm.act(fsm.IDLE, If(start, fsm.next_state(fsm.WAIT_GRANT)))
		fsm.act(fsm.WAIT_GRANT,
			self.req.eq(1),
			If(self.ack,
				seq_start.eq(1),
				fsm.next_state(fsm.WAIT_SEQ)
			)
		)
		fsm.act(fsm.WAIT_SEQ,
			self.req.eq(1),
			If(seq_done, fsm.next_state(fsm.IDLE))
		)
		
		return Fragment(comb, sync) + fsm.get_fragment()
