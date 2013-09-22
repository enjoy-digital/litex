from migen.fhdl.std import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.fhdl.specials import Memory
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.actorlib.fifo import SyncFIFO

class Recorder(Module, AutoCSR):
	def __init__(self, width, depth):
		self.width = width

		self.sink = Sink([("hit", 1), ("d", width)])

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

		fifo = SyncFIFO([("d", width)], depth)
		self.submodules += fifo
	
		# Write fifo is done only when done = 0
		# Fifo must always be pulled by software between
		# acquisition (Todo: add a flush funtionnality)
		self.comb +=[
			fifo.sink.stb.eq(self.sink.stb & ~done),
			fifo.sink.payload.d.eq(self.sink.payload.d),
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
			
			If(self.sink.stb & self.sink.payload.hit & ~done, ongoing.eq(1)
			).Elif(done, ongoing.eq(0)),
		]

		# fifo ack & csr connection
		self.comb += [
			If(~done & ~ongoing & (cnt >= offset), fifo.source.ack.eq(1)
			).Else(fifo.source.ack.eq(self._r_read_en.re & self._r_read_en.r)),
			self._r_read_empty.status.eq(~fifo.source.stb),
			self._r_read_dat.status.eq(fifo.source.payload.d),
			self._r_done.status.eq(done)
		]

		# cnt
		self.sync += [
			If(done == 1,
				cnt.eq(0)
			).Elif(fifo.sink.stb & fifo.sink.ack & ~(fifo.source.stb & fifo.source.ack),
				cnt.eq(cnt+1), 
			)
		]