from migen.fhdl.std import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.fhdl.specials import Memory
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFO
from migen.genlib.fsm import FSM, NextState

from miscope.std import *

class RunLengthEncoder(Module, AutoCSR):
	def __init__(self, width, length):
		self.width = width
		self.length = length

		self.sink = rec_dat(width)
		self.source = rec_dat(width)		

		self._r_enable = CSRStorage()
		
		###

		enable = self._r_enable.storage 
		stb_i = self.sink.stb
		dat_i = self.sink.dat
		ack_i = self.sink.ack

		# Register Input
		stb_i_d = Signal()
		dat_i_d = Signal(width)

		self.sync += [
			If(stb_i,
				dat_i_d.eq(dat_i),
				stb_i_d.eq(stb_i)
			)
		]
		
		# Detect change
		change = Signal()
		self.comb += [change.eq(stb_i & (~enable | (dat_i_d != dat_i)))]

		change_d = Signal()
		change_rising = Signal()
		self.sync += If(stb_i, change_d.eq(change))
		self.comb += change_rising.eq(stb_i & (change & ~change_d))

		# Generate RLE word
		rle_cnt  = Signal(max=length)
		rle_max  = Signal()

		self.comb +=[If(rle_cnt == length, rle_max.eq(enable))]

		self.sync +=[
			If(change | rle_max,
				rle_cnt.eq(0)
			).Else(
				rle_cnt.eq(rle_cnt + 1)
			)
		]

		# Mux RLE word and data
		stb_o = self.source.stb
		dat_o = self.source.dat
		ack_o = self.source.ack

		self.comb +=[
			If(change_rising & ~rle_max,
				stb_o.eq(1),
				dat_o[width-1].eq(1),
				dat_o[:flen(rle_cnt)].eq(rle_cnt)
			).Elif(change_d | rle_max,
				stb_o.eq(stb_i_d),
				dat_o.eq(dat_i_d)
			).Else(
				stb_o.eq(0),
			),
			ack_i.eq(1) #FIXME
		]

class Recorder(Module, AutoCSR):
	def __init__(self, width, depth):
		self.width = width

		self.trig_sink = rec_hit()
		self.dat_sink = rec_dat(width)

		self._r_trigger = CSR()
		self._r_length = CSRStorage(bits_for(depth))
		self._r_offset = CSRStorage(bits_for(depth))
		self._r_done = CSRStatus()

		self._r_read_en = CSR()
		self._r_read_empty = CSRStatus()
		self._r_read_dat = CSRStatus(width)

		###

		fifo = SyncFIFO(width, depth)
		self.submodules += fifo

		fsm = FSM(reset_state="IDLE")
		self.submodules += fsm


		self.comb += [
			self._r_read_empty.status.eq(~fifo.readable),
			self._r_read_dat.status.eq(fifo.dout),
		]

		fsm.act("IDLE",
			If(self._r_trigger.re & self._r_trigger.r,
				NextState("PRE_HIT_RECORDING"),
				fifo.flush.eq(1),
			),
			fifo.re.eq(self._r_read_en.re & self._r_read_en.r),
			self._r_done.status.eq(1)
		)
		
		fsm.act("PRE_HIT_RECORDING",
			fifo.we.eq(self.dat_sink.stb),
			fifo.din.eq(self.dat_sink.dat),
			self.dat_sink.ack.eq(fifo.writable),

			fifo.re.eq(fifo.level >= self._r_offset.storage),

			If(self.trig_sink.stb & self.trig_sink.hit, NextState("POST_HIT_RECORDING"))
		)

		fsm.act("POST_HIT_RECORDING",
			fifo.we.eq(self.dat_sink.stb),
			fifo.din.eq(self.dat_sink.dat),
			self.dat_sink.ack.eq(fifo.writable),

			If(~fifo.writable | (fifo.level >= self._r_length.storage), NextState("IDLE"))
		)
