from migen.fhdl.std import *
from migen.genlib.cdc import MultiReg
from migen.genlib.fifo import _inc
from migen.genlib.record import Record, layout_len
from migen.genlib.misc import optree
from migen.bank.description import *

from milkymist.dvisampler.common import channel_layout

class _SyncBuffer(Module):
	def __init__(self, width, depth):
		self.din = Signal(width)
		self.dout = Signal(width)
		self.re = Signal()

		###

		produce = Signal(max=depth)
		consume = Signal(max=depth)
		storage = Memory(width, depth)
		self.specials += storage

		wrport = storage.get_port(write_capable=True)
		self.specials += wrport
		self.comb += [
			wrport.adr.eq(produce),
			wrport.dat_w.eq(self.din),
			wrport.we.eq(1)
		]
		self.sync += _inc(produce, depth)

		rdport = storage.get_port(async_read=True)
		self.specials += rdport
		self.comb += [
			rdport.adr.eq(consume),
			self.dout.eq(rdport.dat_r)
		]
		self.sync += If(self.re, _inc(consume, depth))

class ChanSync(Module, AutoCSR):
	def __init__(self, nchan=3, depth=8):
		self.valid_i = Signal()
		self.chan_synced = Signal()

		self._r_channels_synced = CSRStatus()

		lst_control = []
		all_control = Signal()
		for i in range(nchan):
			name = "data_in" + str(i)
			data_in = Record(channel_layout, name=name)
			setattr(self, name, data_in)
			name = "data_out" + str(i)
			data_out = Record(channel_layout, name=name)
			setattr(self, name, data_out)

			###
		
			syncbuffer = RenameClockDomains(_SyncBuffer(layout_len(channel_layout), depth), "pix")
			self.submodules += syncbuffer
			self.comb += [
				syncbuffer.din.eq(data_in.raw_bits()),
				data_out.raw_bits().eq(syncbuffer.dout)
			]
			is_control = Signal()
			self.comb += [
				is_control.eq(~data_out.de),
				syncbuffer.re.eq(~is_control | all_control)
			]
			lst_control.append(is_control)

		some_control = Signal()
		self.comb += [
			all_control.eq(optree("&", lst_control)),
			some_control.eq(optree("|", lst_control))
		]
		self.sync.pix += If(~self.valid_i,
				self.chan_synced.eq(0)
			).Else(
				If(some_control,
					If(all_control,
						self.chan_synced.eq(1)
					).Else(
						self.chan_synced.eq(0)
					)
				)
			)
		self.specials += MultiReg(self.chan_synced, self._r_channels_synced.status)
