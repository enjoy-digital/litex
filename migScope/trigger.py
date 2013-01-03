from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.corelogic.misc import optree

class Term:
	# 
	# Definition
	#
	def __init__(self, width, pipe=False):
		self.width = width
		self.pipe = pipe
		self.interface = None
		
		self.reg_name = "term_reg"
		self.reg_base = 0
		self.reg_size = 2*width
		self.words = int(2**bits_for(width-1)/8)
		
		self.i = Signal(self.width)
		self.t = Signal(self.width)
		self.m = Signal(self.width)
		self.o = Signal()
		
	def get_fragment(self):
		frag = [
			self.o.eq((self.m & self.i) == self.t)
			]
		if self.pipe:
			return Fragment(sync=frag)
		else:
			return Fragment(comb=frag)
			
	def connect_to_reg(self, reg):
		comb = []
		comb += [self.t.eq(reg.field.r[0*self.width:1*self.width])]
		comb += [self.m.eq(reg.field.r[1*self.width:2*self.width])]
		return comb
	#	
	#Driver
	#
	def write(self, dat, mask = None):
		if mask == None:
			mask = (2**self.width)-1
		self.interface.write_n(self.reg_base + self.words, dat ,self.width)
		self.interface.write_n(self.reg_base, mask ,self.width)
		
class RangeDetector:
	# 
	# Definition
	#
	def __init__(self, width, pipe=False):
		self.width = width
		self.pipe = pipe
		self.interface = None
		
		self.reg_name = "range_reg"
		self.reg_base = 0
		self.reg_size = 2*width
		self.words = int(2**bits_for(width-1)/8)
		
		self.i = Signal(self.width)
		self.low = Signal(self.width)
		self.high = Signal(self.width)
		self.o = Signal()
		
	def get_fragment(self):
		frag = [
			self.o.eq((self.i >= self.low) & ((self.i <= self.high)))
			]
		if self.pipe:
			return Fragment(sync=frag)
		else:
			return Fragment(comb=frag)
	
	def connect_to_reg(self, reg):
		comb = []
		comb += [self.low.eq(reg.field.r[0*self.width:1*self.width])]
		comb += [self.low.eq(reg.field.r[1*self.width:2*self.width])]
		return comb
	#
	#Driver
	#
	def write_low(self, dat):
		self.interface.write_n(self.reg_base, dat ,self.width)
	
	def write_high(self, dat):
		self.interface.write_n(self.reg_base + self.words, dat ,self.width)

class EdgeDetector:
	# 
	# Definition
	#
	def __init__(self, width, pipe=False, mode = "RFB"):
		self.width = width
		self.pipe = pipe
		self.mode = mode
		self.interface = None
		
		self.reg_name = "edge_reg"
		self.reg_base = 0
		self.reg_size = len(self.mode)*width
		
		self.i = Signal(self.width)
		self.i_d = Signal(self.width)
		if "R" in self.mode:
			self.r_mask = Signal(self.width)
			self.ro = Signal()
		if "F" in self.mode:
			self.f_mask = Signal(self.width)
			self.fo = Signal()
		if "B" in self.mode:
			self.b_mask = Signal(self.width)
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
	
	def connect_to_reg(self, reg):
		comb = []
		i = 0
		if "R" in self.mode:
			comb += [self.r_mask.eq(reg.field.r[i*self.width:(i+1)*self.width])]
			i += 1
		if "F" in self.mode:
			comb += [self.f_mask.eq(reg.field.r[i*self.width:(i+1)*self.width])]
			i += 1
		if "B" in self.mode:
			comb += [self.b_mask.eq(reg.field.r[i*self.width:(i+1)*self.width])]
			i += 1
		return comb
		
	#
	#Driver
	#
	
	def get_offset(self, type):
		if type == "R":
			r = 0
			r = r+self.words if "F" in self.mode else r
			r = r+self.words if "B" in self.mode else r
			return r
		elif type == "F":
			r = 0
			r = r+self.words if "B" in self.mode else r
			return r
		elif type == "B":
			r = 0
			return r
		return 0
			
	def write_r(self, dat):
		self.interface.write_n(self.reg_base + self.get_offset("R"), dat ,self.width)
	
	def write_f(self, dat):
		self.interface.write_n(self.reg_base + self.get_offset("F"), dat ,self.width)
		
	def write_b(self, dat):
		self.interface.write_n(self.reg_base + self.get_offset("B"), dat ,self.width)

class Timer:
	# 
	# Definition
	#
	def __init__(self, width):
		self.width = width
		self.interface = None
		
		self.start = Signal()
		self.stop = Signal()
		self.clear = Signal()
		
		self.enable = Signal()
		self.cnt = Signal(self.width)
		self.cnt_max = Signal(self.width)
		
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
	# 
	# Definition
	#
	def __init__(self,width=4,pipe=False):
		self.width = width
		self.pipe = pipe
		self.interface = None
		
		self._mem = Memory(1, 2**self.width)
		
		self.i = Signal(self.width)
		self._o = Signal()
		self.o = Signal()
		self._lut_port = self._mem.get_port()
		
		self.reg_name = "sum_reg"
		self.reg_base = 0
		self.reg_size = 32
		
		self.prog = Signal()
		self.prog_adr = Signal(width)
		self.prog_dat = Signal()
		self._prog_port = self._mem.get_port(write_capable=True)
		
		
	def get_fragment(self):
		comb = []
		sync = []
		memories = [self._mem]
		comb += [
				self._lut_port.adr.eq(self.i),
				self._o.eq(self._lut_port.dat_r),
				
				self._prog_port.adr.eq(self.prog_adr),
				self._prog_port.we.eq(self.prog),
				self._prog_port.dat_w.eq(self.prog_dat)
		]
		
		
		if self.pipe:
			sync += [self.o.eq(self._o)]
		else:
			comb += [self.o.eq(self._o)]
		return Fragment(comb=comb, sync=sync, memories=memories)
		
	def connect_to_reg(self, reg):
		comb = []
		comb += [
			self.prog_adr.eq(reg.field.r[0:16]),
			self.prog_dat.eq(reg.field.r[16]),
			self.prog.eq(reg.field.r[17])
			]
		return comb
	
	#
	#Driver
	#
	def write(self, truth_table):
		for i in range(len(truth_table)):
			val = truth_table[i]
			we  = 1<<17
			dat = val<<16
			addr = i
			self.interface.write_n(self.reg_base, we + dat + addr,self.reg_size)
			self.interface.write_n(self.reg_base, dat + addr, self.reg_size)
		
class Trigger:
	# 
	# Definition
	#
	def __init__(self, trig_width, ports, address = 0x0000, interface = None):
		self.address = address
		self.trig_width = trig_width
		self.ports = ports
		self.interface = interface
		self.sum = Sum(len(self.ports))
		
		self.in_trig = Signal(self.trig_width)
		
		self.hit = Signal()
		
		# Update port reg_name
		for i in range(len(self.ports)):
			self.ports[i].reg_name += "_%d"%i
		
		# Csr interface
		for port in self.ports:
			setattr(self,port.reg_name,RegisterField(port.reg_name, port.reg_size, reset=0,
				access_bus=WRITE_ONLY, access_dev=READ_ONLY))
		self.sum_reg = RegisterField(self.sum.reg_name, self.sum.reg_size, reset=0, access_bus=WRITE_ONLY, access_dev=READ_ONLY)
		
		self.regs = []
		objects = self.__dict__
		for object in sorted(objects):
			if "_reg" in object:
				self.regs.append(objects[object])
		self.bank = csrgen.Bank(self.regs,address=self.address)
		
		# Update base addr
		self.set_address(self.address)
		
		# Update interface
		self.set_interface(self.interface)
		
	def set_address(self, address):
		self.address = address
		self.bank = csrgen.Bank(self.regs,address=self.address)
		for port in self.ports:
			port.reg_base = self.bank.get_base(port.reg_name)
		self.sum.reg_base = self.bank.get_base(self.sum.reg_name)
		
	def set_interface(self, interface):
		self.interface = interface
		for port in self.ports:
			port.interface = self.interface
		self.sum.interface = self.interface
		
	def get_fragment(self):
		comb = []
		sync = []
		# Connect in_trig to input of trig elements
		comb+= [port.i.eq(self.in_trig) for port in self.ports]
		
		# Connect output of trig elements to sum
		comb+= [self.sum.i[j].eq(self.ports[j].o) for j in range(len(self.ports))]
		
		# Connect sum ouput to hit
		comb+= [self.hit.eq(self.sum.o)]
		
		# Add ports & sum to frag
		frag = self.bank.get_fragment() 
		frag += self.sum.get_fragment()
		for port in self.ports:
			frag += port.get_fragment()
		
		#Connect Registers
		for port in self.ports:
			comb += port.connect_to_reg(getattr(self, port.reg_name))
		comb += self.sum.connect_to_reg(self.sum_reg)
		return frag + Fragment(comb=comb, sync=sync)
