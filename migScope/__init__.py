from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.corelogic.misc import optree

class Term:
	def __init__(self, width, pipe=False):
		self.width = width
		self.pipe = pipe
		
		self.i = Signal(BV(self.width))
		self.t = Signal(BV(self.width))
		self.o = Signal()
	
	def get_fragment(self):
		frag = [
			self.o.eq(self.i==self.t)
			]
		if self.pipe:
			return Fragment(sync=frag)
		else:
			return Fragment(comb=frag)

class RangeDetector:
	def __init__(self, width, pipe=False):
		self.width = width
		self.pipe = pipe

		self.i = Signal(BV(self.width))
		self.low = Signal(BV(self.width))
		self.high = Signal(BV(self.width))
		self.o = Signal()
	
	def get_fragment(self):
		frag = [
			self.o.eq((self.i >= self.low) & ((self.i <= self.high)))
			]
		if self.pipe:
			return Fragment(sync=frag)
		else:
			return Fragment(comb=frag)

class EdgeDetector:
	def __init__(self, width, pipe=False, mode = "RFB"):
		self.width = width
		self.pipe = pipe
		self.mode = mode
		
		self.i = Signal(BV(self.width))
		self.i_d = Signal(BV(self.width))
		if "R" in mode:
			self.r_mask = Signal(BV(self.width))
			self.ro = Signal()
		if "F" in mode:
			self.f_mask = Signal(BV(self.width))
			self.fo = Signal()
		if "B" in mode:
			self.b_mask = Signal(BV(self.width))
			self.bo = Signal()
		self.o = Signal()
	
	def get_fragment(self):
		comb = []
		sync = []
		sync += [self.i_d.eq(self.i)]
		# Rising Edge
		if "R" in self.mode:
			r_eq = [self.ro.eq(self.r_mask & self.i & (~self.i_d))]
			if self.pipe:
				sync += r_eq
			else:
				comb += r_eq
		else:
			comb +=  [self.ro.eq(0)]
		# Falling Edge
		if "F" in self.mode:
			f_eq = [self.fo.eq(self.f_mask & (~ self.i) & self.i_d)]
			if self.pipe:
				sync += f_eq
			else:
				comb += f_eq
		else:
			comb +=  [self.fo.eq(0)]
		# Both
		if "B" in self.mode:
			b_eq = [self.bo.eq(self.b_mask & self.i != self.i_d)]
			if self.pipe:
				sync += b_eq
			else:
				comb += b_eq
		else:
			comb +=  [self.bo.eq(0)]
		#Output
		comb +=  [self.o.eq(self.ro | self.fo | self.bo)]
		
		return Fragment(comb, sync)

class Timer:
	def __init__(self, width):
		self.width = width
		
		self.start = Signal()
		self.stop = Signal()
		self.clear = Signal()
		
		self.enable = Signal()
		self.cnt = Signal(BV(self.width))
		self.cnt_max = Signal(BV(self.width))
		
		self.o = Signal()

	def get_fragment(self):
		comb = []
		sync = []
		sync += [
			If(self.stop,
				self.enable.eq(0),
				self.cnt.eq(0),
				self.o.eq(0)
			).Elif(self.clear,
				self.cnt.eq(0),
				self.o.eq(0)
			).Elif(self.start,
				self.enable.eq(1)
			).Elif(self.enable,
				If(self.cnt <= self.cnt_max,
					self.cnt.eq(self.cnt+1)
				).Else(
					self.o.eq(1)
				)
			),
			If(self.enable,
				self.enable.eq(0),
				self.cnt.eq(0)
			).Elif(self.clear,
				self.cnt.eq(0)
			).Elif(self.start,
				self.enable.eq(1)
			)
			
			]
		
		return Fragment(comb, sync)

class Sum:
	def __init__(self,width=4,pipe=False):
		self.width = width
		self.pipe = pipe
		
		self.i = Signal(BV(self.width))
		self._o = Signal()
		self.o = Signal()
		self._lut_port = MemoryPort(adr=self.i, dat_r=self._o)
		
		self.prog = Signal()
		self.prog_adr = Signal(BV(width))
		self.prog_dat = Signal()
		self._prog_port = MemoryPort(adr=self.prog_adr, we=self.prog, dat_w=self.prog_dat)
		
		self._mem = Memory(1, 2**self.width, self._lut_port, self._prog_port)
		
	def get_fragment(self):
		comb = []
		sync = []
		memories = [self._mem]
		if self.pipe:
			sync += [self.o.eq(self._o)]
		else:
			comb += [self.o.eq(self._o)]
		return Fragment(comb=comb,sync=sync,memories=memories)
		

class Trigger:
	def __init__(self,address, trig_width, dat_width, ports):
		self.address = address
		self.trig_width = trig_width
		self.dat_width = dat_width
		self.ports = ports
		assert (len(self.ports) <= 4), "Nb Ports > 4 (This version support 4 ports Max)"
		self._sum = Sum(len(self.ports))
		
		self.in_trig = Signal(BV(self.trig_width))
		self.in_dat  = Signal(BV(self.dat_width))
		
		self.hit = Signal()
		self.dat = Signal(BV(self.dat_width))
		
		# Csr interface
		for i in range(len(self.ports)):
			if isinstance(self.ports[i],Term):
				setattr(self,"_term_reg%d"%i,RegisterField("rst", 1*self.trig_width, reset=0,
					access_bus=WRITE_ONLY, access_dev=READ_ONLY))
			elif isinstance(self.ports[i],EdgeDetector):
				setattr(self,"_edge_reg%d"%i,RegisterField("rst", 3*self.trig_width, reset=0,
					access_bus=WRITE_ONLY, access_dev=READ_ONLY))
			elif isinstance(self.ports[i],RangeDetector):
				setattr(self,"_range_reg%d"%i,RegisterField("rst", 2*self.trig_width, reset=0,
					access_bus=WRITE_ONLY, access_dev=READ_ONLY))
					
		self._sum_reg = RegisterField("_sum_reg", 17, reset=0,access_bus=WRITE_ONLY, access_dev=READ_ONLY)
		
		regs = []
		objects = self.__dict__
		for object in objects:
			if "_reg" in object:
				regs.append(objects[object])
		regs.append(self._sum_reg)
		self.bank = csrgen.Bank(regs,address=address)
		
	def get_fragment(self):
		comb = []
		sync = []
		# Connect in_trig to input of trig elements
		comb+= [port.i.eq(self.in_trig) for port in self.ports]
		
		# Connect output of trig elements to sum
		# Todo : Add sum tree to have more that 4 inputs
		comb+= [self._sum.i[j].eq(self.ports[j].o) for j in range(len(self.ports))]
		
		# Connect sum ouput to hit
		comb+= [self.hit.eq(self._sum.o)]
		
		# Add ports & sum to frag
		frag = self.bank.get_fragment() 
		frag += self._sum.get_fragment()
		for port in self.ports:
			frag += port.get_fragment()
		comb+= [self.dat.eq(self.in_dat)]
		
		#Connect Registers
		for i in range(len(self.ports)):
			if isinstance(self.ports[i],Term):
				comb += [self.ports[i].t.eq(getattr(self,"_term_reg%d"%i).field.r[0:self.trig_width])]
			elif isinstance(self.ports[i],EdgeDetector):
				comb += [self.ports[i].r_mask.eq(getattr(self,"_edge_reg%d"%i).field.r[0:1*self.trig_width])]
				comb += [self.ports[i].f_mask.eq(getattr(self,"_edge_reg%d"%i).field.r[1*self.trig_width:2*self.trig_width])]
				comb += [self.ports[i].b_mask.eq(getattr(self,"_edge_reg%d"%i).field.r[2*self.trig_width:3*self.trig_width])]
			elif isinstance(self.ports[i],RangeDetector):
				comb += [self.ports[i].low.eq(getattr(self,"_range_reg%d"%i).field.r[0:1*self.trig_width])]
				comb += [self.ports[i].high.eq(getattr(self,"_range_reg%d"%i).field.r[1*self.trig_width:2*self.trig_width])]
				
		comb += [
			self._sum.prog_dat.eq(self._sum_reg.field.r[0:16]),
			self._sum.prog.eq(self._sum_reg.field.r[16]),
			]
		return frag + Fragment(comb=comb, sync=sync)


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
				self.done.eq(0)
			).Elif(self.start,
				self._put_cnt.eq(0),
				self._get_cnt.eq(0),
				self._get_ptr.eq(self._put_ptr-size_minus_offset)
			),
			If(self.put,
				self._put_cnt.eq(self._put_cnt+1),
				self._put_ptr.eq(self._put_ptr+1)
			),
			If(self.get,
				self._get_cnt.eq(self._get_cnt+1),
				self._get_ptr.eq(self._get_ptr+1)
			)
			]
		comb += [
			If(self._put_cnt == size_minus_offset-1,
				self.done.eq(1)
			).Elif(self._get_cnt == size_minus_offset-1,
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
		# Triggers interface
		self.trig_hit  = Signal()
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
			).Elif(self.ctl_arm,
				self.enable.eq(1)
			).Elif(self.rec_done,
				self.enable.eq(0)
			)
			]
		comb += [
			self.rec_offset.eq(self.ctl_offset),
			self.rec_size.eq(self.ctl_size),
			self.rec_start.eq(self.enable & self.trig_hit),
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
		
		self._get = RegisterField("get", reset=1)
		self._get_dat = RegisterField("get_dat", self.width, reset=1,access_bus=READ_ONLY, access_dev=WRITE_ONLY)
		
		regs = [self._rst, self._arm, self._done,
			self._size, self._offset,
			self._get, self._get_dat]
			
		self.bank = csrgen.Bank(regs,address=address)
		
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
			self._done.field.w.eq(self.sequencer.ctl_done)
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

class MigCon:
	pass
	
class MigLa:
	pass

class MigIo:
	def __init__(self, width, mode = "IO"):
		self.width = width
		self.mode = mode
		self.ireg = description.RegisterField("i", 0, READ_ONLY, WRITE_ONLY)
		self.oreg = description.RegisterField("o", 0)
		if "I" in self.mode:
			self.inputs = Signal(BV(self.width))
			self.ireg = description.RegisterField("i", self.width, READ_ONLY, WRITE_ONLY)
			self.ireg.field.w.name_override = "inputs"
		if "O" in self.mode:
			self.outputs = Signal(BV(self.width))
			self.oreg = description.RegisterField("o", self.width)
			self.oreg.field.r.name_override = "ouptuts"
		self.bank = csrgen.Bank([self.oreg, self.ireg])

	def get_fragment(self):
		return self.bank.get_fragment()
