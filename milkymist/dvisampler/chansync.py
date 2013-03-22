from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.genlib.fifo import SyncFIFO
from migen.genlib.misc import optree
from migen.bank.description import *

_control_tokens = [0b1101010100, 0b0010101011, 0b0101010100, 0b1010101011]

class ChanSync(Module, AutoReg):
	def __init__(self, nchan=3, depth=8):
		self.char_synced = Signal()
		self.chan_synced = Signal()

		self._r_channels_synced = RegisterField(1, READ_ONLY, WRITE_ONLY)

		lst_control_starts = []
		all_control_starts = Signal()
		for i in range(nchan):
			name = "data_in" + str(i)
			data_in = Signal(10, name=name)
			setattr(self, name, data_in)
			name = "data_out" + str(i)
			data_out = Signal(10, name=name)
			setattr(self, name, data_out)

			###
		
			fifo = SyncFIFO(10, depth)
			self.add_submodule(fifo, "pix")
			self.comb += [
				fifo.we.eq(self.char_synced),
				fifo.din.eq(data_in),
				data_out.eq(fifo.dout)
			]
			is_control = Signal()
			is_control_r = Signal()
			self.sync.pix += If(fifo.re, is_control_r.eq(is_control))
			control_starts = Signal()
			self.comb += [
				is_control.eq(optree("|", [data_out == t for t in _control_tokens])),
				control_starts.eq(is_control & ~is_control_r),
				fifo.re.eq(~is_control | all_control_starts)
			]
			lst_control_starts.append(control_starts)

		self.comb += all_control_starts.eq(optree("&", lst_control_starts))
		self.sync.pix += If(~self.char_synced,
				self.chan_synced.eq(0)
			).Elif(all_control_starts, self.chan_synced.eq(1))
		self.specials += MultiReg(self.chan_synced, self._r_channels_synced.field.w)
