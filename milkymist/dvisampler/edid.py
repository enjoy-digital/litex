from migen.fhdl.structure import *
from migen.fhdl.specials import Memory, Tristate
from migen.fhdl.module import Module
from migen.genlib.cdc import MultiReg
from migen.genlib.fsm import FSM
from migen.genlib.misc import chooser
from migen.bank.description import AutoReg

_default_edid = [
	0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x3D, 0x17, 0x32, 0x12, 0x2A, 0x6A, 0xBF, 0x00,
	0x05, 0x17, 0x01, 0x03, 0x80, 0x28, 0x1E, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
	0x00, 0x00, 0x00, 0x2E, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
	0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0xE2, 0x0E, 0x20, 0x20, 0x31, 0x58, 0x13, 0x20, 0x20, 0x80,
	0x14, 0x00, 0x28, 0x1E, 0x00, 0x00, 0x00, 0x1E, 0x00, 0x00, 0x00, 0xFC, 0x00, 0x4D, 0x31, 0x20,
	0x44, 0x56, 0x49, 0x20, 0x6D, 0x69, 0x78, 0x65, 0x72, 0x0A, 0x00, 0x00, 0x00, 0x10, 0x00, 0x00,
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x10,
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF,
]

class EDID(Module, AutoReg):
	def __init__(self, pads, default=_default_edid):
		self.specials.mem = Memory(8, 128, init=default)

		###

		scl_i = Signal()
		sda_i = Signal()
		sda_drv = Signal()
		_sda_drv_reg = Signal()
		_sda_i_async = Signal()
		self.sync += _sda_drv_reg.eq(sda_drv)
		self.specials += [
			MultiReg(pads.scl, scl_i),
			Tristate(pads.sda, 0, _sda_drv_reg, _sda_i_async),
			MultiReg(_sda_i_async, sda_i)
		]

		# FIXME: understand what is really going on here and get rid of that workaround
		for x in range(20):
			new_scl = Signal()
			self.sync += new_scl.eq(scl_i)
			scl_i = new_scl
		#

		scl_r = Signal()
		sda_r = Signal()
		scl_rising = Signal()
		sda_rising = Signal()
		sda_falling = Signal()
		self.sync += [
			scl_r.eq(scl_i),
			sda_r.eq(sda_i)
		]
		self.comb += [
			scl_rising.eq(scl_i & ~scl_r),
			sda_rising.eq(sda_i & ~sda_r),
			sda_falling.eq(~sda_i & sda_r)
		]

		start = Signal()
		self.comb += start.eq(scl_i & sda_falling)

		din = Signal(8)
		counter = Signal(max=9)
		self.sync += [
			If(start, counter.eq(0)),
			If(scl_rising,
				If(counter == 8,
					counter.eq(0)
				).Else(
					counter.eq(counter + 1),
					din.eq(Cat(sda_i, din[:7]))
				)
			)
		]

		is_read = Signal()
		update_is_read = Signal()
		self.sync += If(update_is_read, is_read.eq(din[0]))

		offset_counter = Signal(max=128)
		oc_load = Signal()
		oc_inc = Signal()
		self.sync += [
			If(oc_load,
				offset_counter.eq(din)
			).Elif(oc_inc,
				offset_counter.eq(offset_counter + 1)
			)
		]
		rdport = self.mem.get_port()
		self.comb += rdport.adr.eq(offset_counter)
		data_bit = Signal()

		zero_drv = Signal()
		data_drv = Signal()
		self.comb += If(zero_drv, sda_drv.eq(1)).Elif(data_drv, sda_drv.eq(~data_bit))

		data_drv_en = Signal()
		data_drv_stop = Signal()
		self.sync += If(data_drv_en, data_drv.eq(1)).Elif(data_drv_stop, data_drv.eq(0))
		self.sync += If(data_drv_en, chooser(rdport.dat_r, counter, data_bit, 8, reverse=True))

		states = ["WAIT_START",
			"RCV_ADDRESS", "ACK_ADDRESS0", "ACK_ADDRESS1", "ACK_ADDRESS2",
			"RCV_OFFSET", "ACK_OFFSET0", "ACK_OFFSET1", "ACK_OFFSET2",
			"READ", "ACK_READ"]
		fsm = FSM(*states)
		self.submodules += fsm
	
		fsm.act(fsm.RCV_ADDRESS,
			If(counter == 8,
				If(din[1:] == 0x50,
					update_is_read.eq(1),
					fsm.next_state(fsm.ACK_ADDRESS0)
				).Else(
					fsm.next_state(fsm.WAIT_START)
				)
			)
		)
		fsm.act(fsm.ACK_ADDRESS0,
			If(~scl_i, fsm.next_state(fsm.ACK_ADDRESS1))
		)
		fsm.act(fsm.ACK_ADDRESS1,
			zero_drv.eq(1),
			If(scl_i, fsm.next_state(fsm.ACK_ADDRESS2))
		)
		fsm.act(fsm.ACK_ADDRESS2,
			zero_drv.eq(1),
			If(~scl_i,
				If(is_read,
					fsm.next_state(fsm.READ)
				).Else(
					fsm.next_state(fsm.RCV_OFFSET)
				)
			)
		)

		fsm.act(fsm.RCV_OFFSET,
			If(counter == 8,
				oc_load.eq(1),
				fsm.next_state(fsm.ACK_OFFSET0)
			)
		)
		fsm.act(fsm.ACK_OFFSET0,
			If(~scl_i, fsm.next_state(fsm.ACK_OFFSET1))
		)
		fsm.act(fsm.ACK_OFFSET1,
			zero_drv.eq(1),
			If(scl_i, fsm.next_state(fsm.ACK_OFFSET2))
		)
		fsm.act(fsm.ACK_OFFSET2,
			zero_drv.eq(1),
			If(~scl_i, fsm.next_state(fsm.RCV_ADDRESS))
		)

		fsm.act(fsm.READ,
			If(~scl_i,
				If(counter == 8,
					data_drv_stop.eq(1),
					fsm.next_state(fsm.ACK_READ)
				).Else(
					data_drv_en.eq(1)
				)
			)
		)
		fsm.act(fsm.ACK_READ,
			If(scl_rising,
				oc_inc.eq(1),
				If(sda_i,
					fsm.next_state(fsm.WAIT_START)
				).Else(
					fsm.next_state(fsm.READ)
				)
			)
		)

		for state in states:
			fsm.act(getattr(fsm, state), If(start, fsm.next_state(fsm.RCV_ADDRESS)))
