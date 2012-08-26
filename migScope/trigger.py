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
		self._sum_reg = RegisterField("_sum_reg", 32, reset=0,access_bus=WRITE_ONLY, access_dev=READ_ONLY)
		
		regs = []
		objects = self.__dict__
		for object in sorted(objects):
			if "_reg" in object:
				regs.append(objects[object])
		self.bank = csrgen.Bank(regs,address=address)
		
	def get_fragment(self):
		comb = []
		sync = []
		# Connect in_trig to input of trig elements
		comb+= [port.i.eq(self.in_trig) for port in self.ports]
		
		# Connect output of trig elements to sum
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
			self._sum.prog_adr.eq(self._sum_reg.field.r[0:16]),
			self._sum.prog_dat.eq(self._sum_reg.field.r[16]),
			self._sum.prog.eq(self._sum_reg.field.r[17])
			]
		return frag + Fragment(comb=comb, sync=sync)
