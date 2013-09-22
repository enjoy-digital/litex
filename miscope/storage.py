from migen.fhdl.std import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.fhdl.specials import Memory
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.genlib.fifo import SyncFIFO

from miscope.std import *

class RunLenghEncoder(Module, AutoCSR):
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
			dat_i_d.eq(dat_i),
			stb_i_d.eq(stb_i)
		]
		
		# Detect change
		change = Signal()
		comb = [diff.eq(stb_i & (~enable | (dat_i_d != dat_i)))]

		change_d = Signal()
		change_rising = Signal()
		self.sync += change_d.eq(change)
		self.comb += change_rising.eq(change & ~change_d)

		# Generate RLE word
		rle_cnt  = Signal(max=length)
		rle_max  = Signal()

		comb +=[If(rle_cnt == length, rle_max.eq(enable))]

		sync +=[
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

		comb +=[
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

		self.sink = rec_dat_hit(width)

		self._r_trigger = CSR()
		self._r_length = CSRStorage(bits_for(depth))
		self._r_offset = CSRStorage(bits_for(depth))
		self._r_done = CSRStatus()

		self._r_read_en = CSR()
		self._r_read_empty = CSRStatus()
		self._r_read_dat = CSRStatus(width)

		###

		length = self._r_length.storage
		offset = self._r_offset.storage
		done = Signal(reset=1)
		ongoing = Signal()

		cnt = Signal(max=depth)

		fifo = SyncFIFO(width, depth)
		self.submodules += fifo
	
		# Write fifo is done only when done = 0
		# Fifo must always be pulled by software between
		# acquisition (Todo: add a flush funtionnality)
		self.comb +=[
			fifo.we.eq(self.sink.stb & ~done),
			fifo.din.eq(self.sink.dat),
			self.sink.ack.eq(1)
		]

		# Done, Ongoing:
		# 0, 0 : Storage triggered but hit was not yet seen
		#        Data are recorded to fifo, if "offset" datas 
		#        in the fifo, ack is set on fifo.source to
		#        store only "offset" datas.
		#
		# 0, 1 : Hit was seen, ack is no longer set on fifo.source
		#        we are storing "length"-"offset" data in this
		#        phase
		#
		# 1, 0 : We have stored "length" datas in fifo. Write to
		#        fifo is disabled.
		#        Software must now read data from the fifo until
		#        it is empty
		
		# done & ongoing
		self.sync += [
			If(self._r_trigger.re & self._r_trigger.r, done.eq(0)
			).Elif(cnt==length, done.eq(1)),
			
			If(self.sink.stb & self.sink.hit & ~done, ongoing.eq(1)
			).Elif(done, ongoing.eq(0)),
		]

		# fifo ack & csr connection
		self.comb += [
			If(~done & ~ongoing & (cnt >= offset), fifo.re.eq(1)
			).Else(fifo.re.eq(self._r_read_en.re & self._r_read_en.r)),
			self._r_read_empty.status.eq(~fifo.readable),
			self._r_read_dat.status.eq(fifo.dout),
			self._r_done.status.eq(done)
		]

		# cnt
		self.sync += [
			If(done == 1,
				cnt.eq(0)
			).Elif(fifo.we & fifo.writable & ~(fifo.re & fifo.readable),
				cnt.eq(cnt+1), 
			)
		]