from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.corelogic.misc import optree

class Storage:
	def __init__(self, width, depth):
		self.width = width
		self.depth = depth
		self.depth_width = bits_for(self.depth)
		#Control
		self.rst = Signal()
		self.start = Signal()
		self.offset = Signal(BV(self.depth_width))
		self.size = Signal(BV(self.depth_width))
		self.done = Signal()
		self.run = Signal()
		#Write Path
		self.put = Signal()
		self.put_dat = Signal(BV(self.width))
		self._put_cnt = Signal(BV(self.depth_width))
		self._put_ptr = Signal(BV(self.depth_width))
		self._put_port = MemoryPort(adr=self._put_ptr, we=self.put, dat_w=self.put_dat)
		#Read Path
		self.get = Signal()
		self.get_dat = Signal(BV(self.width))
		self._get_cnt = Signal(BV(self.depth_width))
		self._get_ptr = Signal(BV(self.depth_width))
		self._get_port = MemoryPort(adr=self._get_ptr, re=self.get, dat_r=self.get_dat)
		#Others
		self._mem = Memory(self.width, self.depth, self._put_port, self._get_port)
		
		
	def get_fragment(self):
		comb = []
		sync = []
		memories = [self._mem]
		size_minus_offset = Signal(BV(self.depth_width))
		comb += [size_minus_offset.eq(self.size-self.offset)]
		
		#Control
		sync += [
			If(self.rst,
				self._put_cnt.eq(0),
				self._put_ptr.eq(0),
				self._get_cnt.eq(0),
				self._get_ptr.eq(0),
				self.run.eq(0)
			).Elif(self.start & ~self.run,
				self._put_cnt.eq(0),
				self._get_cnt.eq(0),
				self._get_ptr.eq(self._put_ptr-self.offset),
				self.run.eq(1)
			).Elif(self.done,
				self.run.eq(0)
			).Elif(self.put & ~self.done,
				self._put_cnt.eq(self._put_cnt+1),
				self._put_ptr.eq(self._put_ptr+1)
			).Elif(self.get,
				self._get_cnt.eq(self._get_cnt+1),
				self._get_ptr.eq(self._get_ptr+1)
			)
			]
		comb += [
			If((self._put_cnt == size_minus_offset-1) & self.run,
				self.done.eq(1)
			).Else(
				self.done.eq(0)
			)
			]
		return Fragment(comb=comb, sync=sync, memories=memories)

class Sequencer:
	def __init__(self,depth):
		self.depth = depth
		self.depth_width = bits_for(self.depth)
		# Controller interface
		self.ctl_rst = Signal()
		self.ctl_offset = Signal(BV(self.depth_width))
		self.ctl_size = Signal(BV(self.depth_width))
		self.ctl_arm = Signal()
		self.ctl_done = Signal()
		self._ctl_arm_d = Signal()
		# Triggers interface
		self.trig_hit  = Signal()
		self._trig_hit_d = Signal()
		# Recorder interface
		self.rec_offset = Signal(BV(self.depth_width))
		self.rec_size = Signal(BV(self.depth_width))
		self.rec_start = Signal()
		self.rec_done  = Signal()
		# Others
		self.enable = Signal()
		
	def get_fragment(self):
		comb = []
		sync = []
		#Control
		sync += [
			If(self.ctl_rst,
				self.enable.eq(0)
			).Elif(self.ctl_arm & ~self._ctl_arm_d,
				self.enable.eq(1)
			).Elif(self.rec_done,
				self.enable.eq(0)
			),
			self._ctl_arm_d.eq(self.ctl_arm)
			]
		sync += [self._trig_hit_d.eq(self.trig_hit)]
		comb += [
			self.rec_offset.eq(self.ctl_offset),
			self.rec_size.eq(self.ctl_size),
			self.rec_start.eq(self.enable & (self.trig_hit & ~self._trig_hit_d)),
			self.ctl_done.eq(~self.enable)
			]
		return Fragment(comb=comb, sync=sync)

class Recorder:
	def __init__(self,address, width, depth):
		self.address = address
		self.width = width
		self.depth = depth
		self.depth_width = bits_for(self.depth)
		
		self.storage = Storage(self.width, self.depth)
		self.sequencer = Sequencer(self.depth)
		
		# Csr interface
		self._rst = RegisterField("rst", reset=1)
		self._arm = RegisterField("arm", reset=0)
		self._done = RegisterField("done", reset=0, access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		
		self._size = RegisterField("size", self.depth_width, reset=1)
		self._offset = RegisterField("offset", self.depth_width, reset=1)
		
		self._get = RegisterField("get", reset=0)
		self._get_dat = RegisterField("get_dat", self.width, reset=1,access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		
		regs = [self._rst, self._arm, self._done,
			self._size, self._offset,
			self._get, self._get_dat]
			
		self.bank = csrgen.Bank(regs,address=self.address)
		
		# Trigger Interface
		self.trig_hit = Signal()
		self.trig_dat = Signal(BV(self.width))
		
	def get_fragment(self):
		comb = []
		sync = []

		#Bank <--> Storage / Sequencer
		comb += [
			self.sequencer.ctl_rst.eq(self._rst.field.r),
			self.storage.rst.eq(self._rst.field.r),
			self.sequencer.ctl_offset.eq(self._offset.field.r),
			self.sequencer.ctl_size.eq(self._size.field.r),
			self.sequencer.ctl_arm.eq(self._arm.field.r),
			self._done.field.w.eq(self.sequencer.ctl_done),
			self.storage.get.eq(self._get.field.r),
			self._get_dat.field.w.eq(self.storage.get_dat)
			]
		
		#Storage <--> Sequencer <--> Trigger
		comb += [
			self.storage.offset.eq(self.sequencer.rec_offset),
			self.storage.size.eq(self.sequencer.rec_size),
			self.storage.start.eq(self.sequencer.rec_start),
			self.sequencer.rec_done.eq(self.storage.done),
			self.sequencer.trig_hit.eq(self.trig_hit),
			self.storage.put.eq(self.sequencer.enable),
			self.storage.put_dat.eq(self.trig_dat)
			
			]

		return self.bank.get_fragment()+\
			self.storage.get_fragment()+self.sequencer.get_fragment()+\
			Fragment(comb=comb, sync=sync)
