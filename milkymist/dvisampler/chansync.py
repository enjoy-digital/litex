from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.genlib.fifo import SyncFIFO
from migen.genlib.record import Record
from migen.genlib.misc import optree
from migen.bank.description import *

from milkymist.dvisampler.common import channel_layout

class ChanSync(Module, AutoCSR):
	def __init__(self, nchan=3, depth=8):
		self.valid_i = Signal()
		self.chan_synced = Signal()

		self._r_channels_synced = CSRStatus()

		lst_control_starts = []
		all_control_starts = Signal()
		for i in range(nchan):
			name = "data_in" + str(i)
			data_in = Record(channel_layout, name=name)
			setattr(self, name, data_in)
			name = "data_out" + str(i)
			data_out = Record(channel_layout, name=name)
			setattr(self, name, data_out)

			###
		
			fifo = SyncFIFO(10, depth)
			self.add_submodule(fifo, "pix")
			self.comb += [
				fifo.we.eq(self.valid_i),
				fifo.din.eq(data_in.raw_bits()),
				data_out.raw_bits().eq(fifo.dout)
			]
			is_control = Signal()
			is_control_r = Signal()
			self.sync.pix += If(fifo.readable & fifo.re, is_control_r.eq(is_control))
			control_starts = Signal()
			self.comb += [
				is_control.eq(~data_out.de),
				control_starts.eq(is_control & ~is_control_r),
				fifo.re.eq(~is_control | all_control_starts)
			]
			lst_control_starts.append(control_starts)

		some_control_starts = Signal()
		self.comb += [
			all_control_starts.eq(optree("&", lst_control_starts)),
			some_control_starts.eq(optree("|", lst_control_starts))
		]
		self.sync.pix += If(~self.valid_i,
				self.chan_synced.eq(0)
			).Else(
				If(some_control_starts,
					If(all_control_starts,
						self.chan_synced.eq(1)
					).Else(
						self.chan_synced.eq(0)
					)
				)
			)
		self.specials += MultiReg(self.chan_synced, self._r_channels_synced.status)
