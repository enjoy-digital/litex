from migen.fhdl.std import *
from migen.bank.description import *

class Bandwidth(Module, AutoCSR):
	def __init__(self, cmd, period_bits=24):
		self._r_update = CSR()
		self._r_nreads = CSRStatus(period_bits)
		self._r_nwrites = CSRStatus(period_bits)

		###

		cmd_stb = Signal()
		cmd_ack = Signal()
		cmd_is_read = Signal()
		cmd_is_write = Signal()
		self.sync += [
			cmd_stb.eq(cmd.stb),
			cmd_ack.eq(cmd.ack),
			cmd_is_read.eq(cmd.is_read),
			cmd_is_write.eq(cmd.is_write)
		]

		counter = Signal(period_bits)
		period = Signal()
		nreads = Signal(period_bits)
		nwrites = Signal(period_bits)
		nreads_r = Signal(period_bits)
		nwrites_r = Signal(period_bits)
		self.sync += [
			Cat(counter, period).eq(counter + 1),
			If(period,
				nreads_r.eq(nreads),
				nwrites_r.eq(nwrites),
				nreads.eq(0),
				nwrites.eq(0)
			).Elif(cmd_stb & cmd_ack,
				If(cmd_is_read, nreads.eq(nreads + 1)),
				If(cmd_is_write, nwrites.eq(nwrites + 1)),
			),
			If(self._r_update.re,
				self._r_nreads.status.eq(nreads_r),
				self._r_nwrites.status.eq(nwrites_r)
			)
		]
