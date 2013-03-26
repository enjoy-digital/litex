from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.genlib.misc import optree
from migen.genlib.fsm import *

from miscope.tools.misc import RisingEdge

class Storage:
	# 
	# Definition
	#
	def __init__(self, width, depth):
		self.width = width
		self.depth = depth
		self.depth_width = bits_for(self.depth)
		
		# Control
		self.rst = Signal()
		self.start = Signal()
		self.offset = Signal(self.depth_width)
		self.size = Signal(self.depth_width)
		self.done = Signal()
		
		# Push Path
		self.push_stb = Signal()
		self.push_dat = Signal(self.width)
		self._push_ptr = Signal(self.depth_width)
		self._push_ptr_stop = Signal(self.depth_width)
		
		# Pull Path
		self.pull_stb = Signal()
		self.pull_dat = Signal(self.width)
		self._pull_ptr = Signal(self.depth_width)
		
		# Memory
		self._mem = Memory(self.width, self.depth)
		self._push_port = self._mem.get_port(write_capable=True)
		self._pull_port = self._mem.get_port(has_re=True)
		
	def get_fragment(self):
		comb = [
					self._push_port.adr.eq(self._push_ptr),
					self._push_port.we.eq(self.push_stb),
					self._push_port.dat_w.eq(self.push_dat),
		
					self._pull_port.adr.eq(self._pull_ptr),
					self._pull_port.re.eq(self.pull_stb),
					self.pull_dat.eq(self._pull_port.dat_r)
		]
		
		# FSM
		fsm = FSM("IDLE", "ACTIVE")
		
		# Idle
		fsm.act(fsm.IDLE, 
			If(self.start, 
				fsm.next_state(fsm.ACTIVE),
			)
		)
		
		# Active
		fsm.act(fsm.ACTIVE,
			If(self.done | self.rst,
				fsm.next_state(fsm.IDLE),
			)
		)
		
		sync =[ 
			If(fsm.entering(fsm.ACTIVE),
				self._push_ptr_stop.eq(self._push_ptr + self.size - self.offset),
				self._pull_ptr.eq(self._push_ptr - self.offset - 1)	
			).Else(
				If(self.pull_stb, self._pull_ptr.eq(self._pull_ptr + 1))
			),
			If(self.push_stb, self._push_ptr.eq(self._push_ptr + 1)),
		]
		comb +=[self.done.eq((self._push_ptr == self._push_ptr_stop) & fsm.ongoing(fsm.ACTIVE))]
		
		return Fragment(comb, sync, specials={self._mem}) + fsm.get_fragment()

class RLE:

	# 
	# Definition
	#
	def __init__(self, width, length):
		self.width = width
		self.length = length

		# Control
		self.enable = Signal()

		# Input
		self.dat_i = Signal(width)

		# Output
		self.stb_o = Signal()
		self.dat_o = Signal(width)
		
	def get_fragment(self):

		# Register Input		
		dat_i_d = Signal(self.width)

		sync =[dat_i_d.eq(self.dat_i)]

		# Detect diff
		diff = Signal()
		comb = [diff.eq(~self.enable | (dat_i_d != self.dat_i))]

		diff_rising = RisingEdge(diff)
		diff_d = Signal()
		sync +=[diff_d.eq(diff)]

		# Generate RLE word
		rle_cnt  = Signal(max=self.length)
		rle_max  = Signal()

		comb +=[If(rle_cnt == self.length, rle_max.eq(self.enable))]

		sync +=[
			If(diff | rle_max,
				rle_cnt.eq(0)
			).Else(
				rle_cnt.eq(rle_cnt + 1)
			)
		]

		# Mux RLE word and data
		comb +=[
			If(diff_rising.o & (~rle_max),
				self.stb_o.eq(1),
				self.dat_o[self.width-1].eq(1),
				self.dat_o[:len(rle_cnt)].eq(rle_cnt)
			).Elif(diff_d | rle_max,
				self.stb_o.eq(1),
				self.dat_o.eq(dat_i_d)
			).Else(
				self.stb_o.eq(0),
			)
		]

		return Fragment(comb, sync) + diff_rising.get_fragment()

class Sequencer:
	# 
	# Definition
	#
	def __init__(self):
		
		# Control
		self.rst = Signal()
		self.arm = Signal()
		
		# Trigger
		self.hit  = Signal()
		
		# Recorder
		self.start = Signal()
		self.done = Signal()
		
		# Internal
		self.enable = Signal()
		
	def get_fragment(self):
		
		# FSM
		fsm = FSM("IDLE", "ACTIVE")
		
		# Idle
		fsm.act(fsm.IDLE, 
			If(self.arm, 
				fsm.next_state(fsm.ACTIVE),
			)
		)
		
		# Active
		fsm.act(fsm.ACTIVE,
			If(self.done | self.rst,
				fsm.next_state(fsm.IDLE),
			),
			self.enable.eq(1)
		)
		
		# Start
		hit_rising = RisingEdge(self.hit)
		comb =[self.start.eq(self.enable & hit_rising.o)]

		return Fragment(comb) + fsm.get_fragment() + hit_rising.get_fragment()


REC_RST_BASE		= 0x00
REC_RLE_BASE        = 0x01
REC_ARM_BASE		= 0x02
REC_DONE_BASE		= 0x03
REC_SIZE_BASE		= 0x04
REC_OFFSET_BASE		= 0x06
REC_READ_BASE		= 0x08
REC_READ_DATA_BASE	= 0x09

class Recorder:
	# 
	# Definition
	#
	def __init__(self, width, depth, address=0x0000, interface=None):
		self.width = width
		self.depth = depth
		self.depth_width = bits_for(self.depth-1)
		
		self.storage = Storage(self.width, self.depth)
		self.sequencer = Sequencer()
		self.rle = RLE(self.width, (2**(width-2)))
		
		# csr interface
		self._r_rst = RegisterField(reset=1)
		self._r_rle = RegisterField(reset=0)
		self._r_arm = RegisterField(reset=0)
		self._r_done = RegisterField(reset=0, access_bus=READ_ONLY, 
									access_dev=WRITE_ONLY)
		
		self._r_size = RegisterField(self.depth_width, reset=1)
		self._r_offset = RegisterField(self.depth_width, reset=1)
		
		self._r_pull_stb = RegisterField(reset=0)
		self._r_pull_dat = RegisterField(self.width, reset=1, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		
		self.regs = [self._r_rst, self._r_rle, self._r_arm, self._r_done, self._r_size, self._r_offset,
					self._r_pull_stb, self._r_pull_dat]
		
		# set address / interface
		self.set_address(address)
		self.set_interface(interface)
		
		# trigger Interface
		self.hit = Signal()
		self.dat = Signal(self.width)
	
	def set_address(self, address):
		self.address = address
		self.bank = csrgen.Bank(self.regs, address=self.address)
			
	def set_interface(self, interface):
		self.interface = interface
		
	def get_fragment(self):

		_pull_stb_rising = RisingEdge(self._r_pull_stb.field.r)

		# Bank <--> Storage / Sequencer
		comb = [
			self.sequencer.rst.eq(self._r_rst.field.r),
			self.storage.rst.eq(self._r_rst.field.r),
			
			self.rle.enable.eq(self._r_rle.field.r),
			self.sequencer.arm.eq(self._r_arm.field.r),
			self.storage.offset.eq(self._r_offset.field.r),
			self.storage.size.eq(self._r_size.field.r),

			self._r_done.field.w.eq(~self.sequencer.enable),
			
			self.storage.pull_stb.eq(_pull_stb_rising.o),
			self._r_pull_dat.field.w.eq(self.storage.pull_dat)
			]
		
		# Storage <--> Sequencer <--> Trigger
		comb += [
			self.storage.start.eq(self.sequencer.start),
			self.sequencer.done.eq(self.storage.done),
			self.sequencer.hit.eq(self.hit),
			
			self.rle.dat_i.eq(self.dat),

			self.storage.push_stb.eq(self.sequencer.enable & self.rle.stb_o),
			self.storage.push_dat.eq(self.rle.dat_o)
			]
		
		return self.bank.get_fragment() + Fragment(comb) +\
			self.storage.get_fragment() + self.sequencer.get_fragment() +\
			_pull_stb_rising.get_fragment() + self.rle.get_fragment()

			
			
	#
	# Driver
	#
	def reset(self):
		self.interface.write(self.bank.get_base() + REC_RST_BASE, 1)
		self.interface.write(self.bank.get_base() + REC_RST_BASE, 0)

	def enable_rle(self):
		self.interface.write(self.bank.get_base() + REC_RLE_BASE, 1)

	def disable_rle(self):
		self.interface.write(self.bank.get_base() + REC_RLE_BASE, 0)

	def arm(self):
		self.interface.write(self.bank.get_base() + REC_ARM_BASE, 1)
		self.interface.write(self.bank.get_base() + REC_ARM_BASE, 0)
	
	def is_done(self):
		return self.interface.read(self.bank.get_base() + REC_DONE_BASE) == 1
		
	def set_size(self, dat):
		self.interface.write_n(self.bank.get_base() + REC_SIZE_BASE, dat, 16)
		
	def set_offset(self, dat):
		self.interface.write_n(self.bank.get_base() + REC_OFFSET_BASE, dat, 16)
		
	def pull(self, size):
		r = []
		for i in range(size):
			self.interface.write(self.bank.get_base() + REC_READ_BASE, 1)
			self.interface.write(self.bank.get_base() + REC_READ_BASE, 0)
			r.append(self.interface.read_n(self.bank.get_base() + REC_READ_DATA_BASE, self.width))
		return r
