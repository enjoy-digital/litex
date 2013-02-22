from migen.fhdl.structure import *
from migen.bus import csr
from migen.bank import description, csrgen
from migen.bank.description import *
from migen.corelogic.misc import optree


class RegParams:
	def __init__(self, name, base, width, nb):
		self.name = name
		self.base = base
		self.width = width
		self.nb = nb
		
		self.size = nb*width
		self.words = int(2**bits_for(self.width-1)/8)

def list_regs(objects):
		r = []
		for object in objects:
			if "_reg" in object:
				r.append(objects[object])
		return r

class Term:
	#
	# Definition
	#
	def __init__(self, width):
		self.width = width
		self.interface = None
		
		self.i = Signal(width)
		self.t = Signal(width)
		self.m = Signal(width)
		self.o = Signal()
		
		self.reg_p = RegParams("term_reg", 0, width, 2)
	
	def get_registers(self, reg):
		comb = [self.t.eq(reg.field.r[0*self.width:1*self.width])]
		comb += [self.m.eq(reg.field.r[1*self.width:2*self.width])]
		return comb
	
	def get_fragment(self, reg):
		comb = [self.o.eq((self.m & self.i) == self.t)]
		comb += self.get_registers(reg)
		return Fragment(comb)
	
	#
	# Driver
	#
	def write(self, dat, mask=None):
		if mask is None:
			mask = (2**self.width)-1
		self.interface.write_n(self.reg_p.base + self.reg_p.words, dat, self.width)
		self.interface.write_n(self.reg_p.base, mask, self.width)
		
class RangeDetector:
	# 
	# Definition
	#
	def __init__(self, width):
		self.width = width
		self.pipe = pipe
		self.interface = None
		
		self.reg_p = RegParams("range_reg", 0, width, 2)
		
		self.i = Signal(width)
		self.low = Signal(width)
		self.high = Signal(width)
		self.o = Signal()
		
	def get_registers(self, reg):
		comb = [self.low.eq(reg.field.r[0*self.width:1*self.width])]
		comb += [self.low.eq(reg.field.r[1*self.width:2*self.width])]
		return comb
		
	def get_fragment(self, reg):
		comb = [self.o.eq((self.i >= self.low) & (self.i <= self.high))]
		comb += self.get_registers(reg)
		return Fragment(comb)
	#
	# Driver
	#
	def write_low(self, dat):
		self.interface.write_n(self.reg_p.base, dat ,self.width)
	
	def write_high(self, dat):
		self.interface.write_n(self.reg_p.base + self.reg_p.words, dat ,self.width)

class EdgeDetector:
	# 
	# Definition
	#
	def __init__(self, width, mode = "RFB"):
		self.width = width
		self.mode = mode
		self.interface = None
		
		self.reg_p = RegParams("edge_reg", 0, width, len(self.mode)
		
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
	
	def get_registers(self, reg):
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
	
	def get_fragment(self, reg):
		comb = []
		sync = [self.i_d.eq(self.i)]
		
		# Rising Edge
		if "R" in self.mode:
			comb += [self.ro.eq(self.r_mask & self.i & (~self.i_d))]
		else:
			comb += [self.ro.eq(0)]
			
		# Falling Edge
		if "F" in self.mode:
			comb += [self.fo.eq(self.f_mask & (~ self.i) & self.i_d)]
		else:
			comb += [self.fo.eq(0)]
			
		# Both
		if "B" in self.mode:
			comb += [self.bo.eq(self.b_mask & self.i != self.i_d)]
		else:
			comb += [self.bo.eq(0)]
			
		# Output
		comb += [self.o.eq(self.ro | self.fo | self.bo)]
		
		# Registers
		comb += self.get_registers(reg)
		
		return Fragment(comb, sync)
		
	#
	# Driver
	#
	def get_offset(self, type):
		if type == "R":
			r = 0
			r = r + self.words if "F" in self.mode else r
			r = r + self.words if "B" in self.mode else r
			return r
		elif type == "F":
			r = 0
			r = r + self.words if "B" in self.mode else r
			return r
		elif type == "B":
			r = 0
			return r
		return 0
			
	def write_r(self, dat):
		self.interface.write_n(self.reg_p.base + self.get_offset("R"), dat ,self.width)
	
	def write_f(self, dat):
		self.interface.write_n(self.reg_p.base + self.get_offset("F"), dat ,self.width)
		
	def write_b(self, dat):
		self.interface.write_n(self.reg_p.base + self.get_offset("B"), dat ,self.width)

class Sum:
	#
	# Definition
	#
	def __init__(self, width=4):
		self.width = width
		self.interface = None
		
		
		
		self.i = Signal(self.width)
		self._o = Signal()
		self.o = Signal()
		
		self.reg_p = RegParams("sum_reg", 0, 8, 4)
		
		self.prog_stb = Signal()
		self.prog_adr = Signal(width)
		self.prog_dat = Signal()
		
		self._mem = Memory(1, 2**self.width)
		self._lut_port = self._mem.get_port()
		self._prog_port = self._mem.get_port(write_capable=True)
	
	def get_registers(self, reg):
		comb = [
			self.prog_adr.eq(reg.field.r[0:16]),
			self.prog_dat.eq(reg.field.r[16]),
			self.prog_stb.eq(reg.field.r[17])
			]
		return comb
	
	def get_fragment(self, reg):
		comb = [
				self._lut_port.adr.eq(self.i),
				self._o.eq(self._lut_port.dat_r),
				
				self._prog_port.adr.eq(self.prog_adr),
				self._prog_port.we.eq(self.prog_stb),
				self._prog_port.dat_w.eq(self.prog_dat)
				
				self.o.eq(self._o)
		]
		comb += get_registers(reg)
		return Fragment(comb, sync, memories=self._mem)
	
	#
	#Driver
	#
	def write(self, truth_table):
		for i in range(len(truth_table)):
			val = truth_table[i]
			we = 1<<17
			dat = val<<16
			addr = i
			self.interface.write_n(self.reg_p.base, we + dat + addr, self.reg_size)
			self.interface.write_n(self.reg_p.base, dat + addr, self.reg_size)
		
class Trigger:
	# 
	# Definition
	#
	def __init__(self, trig_w, ports, address=0x0000, interface=None):
		self.trig_w = trig_w
		self.ports = ports
		
		self.sum = Sum(len(ports))
		self.trig = Signal(self.trig_w)
		self.hit = Signal()
		
		# insert port number in port reg name
		for i in range(len(self.ports)):
			self.ports[i].reg_p.name += "_%d"%i
		
		# generate ports csr registers fields
		for port in self.ports:
			rf = RegisterField(port.reg_p.name, port.reg_p.size, reset=0,
												 access_bus=WRITE_ONLY, access_dev=READ_ONLY)
			setattr(self, port.reg_name, rf)
		
		# generate sum csr registers fields
		self.sum_reg = RegisterField(self.sum.reg_p.name, self.sum.reg_p.size, reset=0,
																 access_bus=WRITE_ONLY, access_dev=READ_ONLY)

		# generate registers
		self.regs = list_regs(self.__dict__)
		self.bank = csrgen.Bank(self.regs, address=address)
		
		# update base addr & interface
		self.set_address(self.address)
		self.set_interface(self.interface)
		
	def set_address(self, address):
		self.address = address
		self.bank = csrgen.Bank(self.regs,address=self.address)
		for port in self.ports:
			port.reg_p.base = self.bank.get_base(port.reg_p.name)
		self.sum.reg_p.base = self.bank.get_base(self.sum.reg_p.name)
		
	def set_interface(self, interface):
		self.interface = interface
		for port in self.ports:
			port.interface = self.interface
		self.sum.interface = self.interface
		
	def get_fragment(self):
		# connect trig to input of each trig element
		comb = [port.i.eq(self.in_trig) for port in self.ports]
		
		# connect output of trig elements to sum
		comb += [self.sum.i[j].eq(self.ports[j].o) for j in range(len(self.ports))]
		
		# connect sum ouput to hit
		comb += [self.hit.eq(self.sum.o)]
		
		# add ports & sum to frag
		frag = self.bank.get_fragment() 
		frag += self.sum.get_fragment(self.sum_reg)
		for port in self.ports:
			frag += port.get_fragment(getattr(self, port.reg_name))
			
		return frag + Fragment(comb)
