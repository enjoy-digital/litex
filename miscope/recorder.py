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
				self._pull_ptr.eq(self._push_ptr-self.offset - 1)	
			).Else(
				If(self.pull_stb, self._pull_ptr.eq(self._pull_ptr + 1))
			),
			If(self.push_stb, self._push_ptr.eq(self._push_ptr + 1)),
		]
		comb +=[self.done.eq((self._push_ptr == self._push_ptr_stop) & fsm.ongoing(fsm.ACTIVE))]
		
		return Fragment(comb, sync, specials={self._mem}) + fsm.get_fragment()

class Sequencer:
	# 
	# Definition
	#
	def __init__(self,depth):
		self.depth = depth
		self.depth_width = bits_for(self.depth)
		
		# Controller interface
		self.ctl_rst = Signal()
		self.ctl_offset = Signal(self.depth_width)
		self.ctl_size = Signal(self.depth_width)
		self.ctl_arm = Signal()
		self.ctl_done = Signal()
		self._ctl_arm_d = Signal()
		
		# Trigger interface
		self.hit  = Signal()
		
		# Recorder interface
		self.rec_offset = Signal(self.depth_width)
		self.rec_size = Signal(self.depth_width)
		self.rec_start = Signal()
		self.rec_done  = Signal()
		
		# Others
		self.enable = Signal()
		
	def get_fragment(self):
		
		# FSM
		fsm = FSM("IDLE", "ACTIVE")
		
		# Idle
		fsm.act(fsm.IDLE, 
			If(self.ctl_arm, 
				fsm.next_state(fsm.ACTIVE),
			)
		)
		
		# Active
		fsm.act(fsm.ACTIVE,
			If(self.rec_done | self.ctl_rst,
				fsm.next_state(fsm.IDLE),
			),
			self.enable.eq(1)
		)
		
		hit_rising = RisingEdge(self.hit)
		
		# connexion
		comb = [
			self.rec_offset.eq(self.ctl_offset),
			self.rec_size.eq(self.ctl_size),
			self.rec_start.eq(self.enable & hit_rising.o),
			self.ctl_done.eq(~self.enable),
			]
		return Fragment(comb) + fsm.get_fragment() + hit_rising.get_fragment()


REC_RST_BASE		= 0x00
REC_ARM_BASE		= 0x01
REC_DONE_BASE		= 0x02
REC_SIZE_BASE		= 0x03
REC_OFFSET_BASE		= 0x05
REC_READ_BASE		= 0x07
REC_READ_DATA_BASE	= 0x08

class Recorder:
	# 
	# Definition
	#
	def __init__(self, width, depth, address=0x0000, interface=None):
		self.width = width
		self.depth = depth
		self.depth_width = bits_for(self.depth-1)
		
		self.storage = Storage(self.width, self.depth)
		self.sequencer = Sequencer(self.depth)
		
		# csr interface
		self._rst = RegisterField("rst", reset=1)
		self._arm = RegisterField("arm", reset=0)
		self._done = RegisterField("done", reset=0, access_bus=READ_ONLY, 
									access_dev=WRITE_ONLY)
		
		self._size = RegisterField("size", self.depth_width, reset=1)
		self._offset = RegisterField("offset", self.depth_width, reset=1)
		
		self._pull_stb = RegisterField("pull_stb", reset=0)
		self._pull_dat = RegisterField("pull_dat", self.width, reset=1, 
										access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		
		self.regs = [self._rst, self._arm, self._done, self._size, self._offset,
					self._pull_stb, self._pull_dat]
		
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

		_pull_stb_rising = RisingEdge(self._pull_stb.field.r)

		# Bank <--> Storage / Sequencer
		comb = [
			self.sequencer.ctl_rst.eq(self._rst.field.r),
			self.storage.rst.eq(self._rst.field.r),
			
			self.sequencer.ctl_offset.eq(self._offset.field.r),
			self.sequencer.ctl_size.eq(self._size.field.r),
			self.sequencer.ctl_arm.eq(self._arm.field.r),
			
			self._done.field.w.eq(self.sequencer.ctl_done),
			
			self.storage.pull_stb.eq(_pull_stb_rising.o),
			self._pull_dat.field.w.eq(self.storage.pull_dat)
			]
		
		# Storage <--> Sequencer <--> Trigger
		comb += [
			self.storage.offset.eq(self.sequencer.rec_offset),
			self.storage.size.eq(self.sequencer.rec_size),
			self.storage.start.eq(self.sequencer.rec_start),
			
			self.sequencer.rec_done.eq(self.storage.done),
			self.sequencer.hit.eq(self.hit),
			
			self.storage.push_stb.eq(self.sequencer.enable),
			self.storage.push_dat.eq(self.dat)
			]
		
		return self.bank.get_fragment() + Fragment(comb) +\
			self.storage.get_fragment() + self.sequencer.get_fragment() +\
			_pull_stb_rising.get_fragment()
			
	#
	# Driver
	#
	def reset(self):
		self.interface.write(self.bank.get_base() + REC_RST_BASE, 1)
		self.interface.write(self.bank.get_base() + REC_RST_BASE, 0)
	
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
