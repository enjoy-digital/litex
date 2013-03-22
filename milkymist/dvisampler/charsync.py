from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.genlib.misc import optree
from migen.bank.description import *

_control_tokens = [0b1101010100, 0b0010101011, 0b0101010100, 0b1010101011]

class CharSync(Module, AutoReg):
	def __init__(self, required_controls=8):
		self.raw_data = Signal(10)
		self.synced = Signal()
		self.data = Signal(10)

		self._r_char_synced = RegisterField(1, READ_ONLY, WRITE_ONLY)

		###

		raw_data1 = Signal(10)
		self.sync.pix += raw_data1.eq(self.raw_data)
		raw = Signal(20)
		self.comb += raw.eq(Cat(raw_data1, self.raw_data))

		found_control = Signal()
		control_position = Signal(max=10)
		for i in range(10):
			self.sync.pix += If(optree("|", [raw[i:i+10] == t for t in _control_tokens]),
			  	found_control.eq(1),
			  	control_position.eq(i)
			)

		control_counter = Signal(max=required_controls)
		previous_control_position = Signal(max=10)
		word_sel = Signal(max=10)
		self.sync.pix += [
			If(found_control & (control_position == previous_control_position),
				If(control_counter == (required_controls - 1),
					control_counter.eq(0),
					self.synced.eq(1),
					word_sel.eq(control_position)
				).Else(
					control_counter.eq(control_counter + 1)
				)
			).Else(
				control_counter.eq(0)
			),
			previous_control_position.eq(control_position)
		]
		self.specials += MultiReg(self.synced, self._r_char_synced.field.w)

		self.sync.pix += self.data.eq(raw >> word_sel)
