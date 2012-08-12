from migen.fhdl.structure import *
from migen.bank import description, csrgen
from migen.bank.description import READ_ONLY, WRITE_ONLY

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
			if self.pipe:
				sync += [self.ro.eq(self.i & (~self.i_d))]
			else:
				comb +=  [self.ro.eq(self.i & (~ self.i_d))]
		else:
			comb +=  [self.ro.eq(0)]
		# Falling Edge
		if "F" in self.mode:
			if self.pipe:
				sync += [self.fo.eq((~ self.i) & self.i_d)]
			else:
				comb +=  [self.fo.eq((~ self.i) & self.i_d)]
		else:
			comb +=  [self.fo.eq(0)]
		# Both
		if "B" in self.mode:
			if self.pipe:
				sync += [self.bo.eq(self.i != self.i_d)]
			else:
				comb +=  [self.bo.eq(self.i != self.i_d)]
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
	def __init__(self,size=4,pipe=False,prog_mode="PAR"):
		self.size = size
		self.pipe = pipe
		self.prog_mode = prog_mode
		assert (size <= 4), "size > 4 (This version support only non cascadable SRL16)"
		self.i0 = Signal()
		self.i1 = Signal()
		self.i2 = Signal()
		self.i3 = Signal()
		
		self._ce = Signal()
		self._shift_in = Signal()
		
		self.o = Signal()
		self._o = Signal()
		
		if self.prog_mode == "PAR":
			self.prog =  Signal()
			self.prog_dat = Signal(BV(16))
			self._shift_dat = Signal(BV(17))
			self._shift_cnt = Signal(BV(4))
		elif self.prog_mode == "SHIFT":
			self.shift_ce = Signal()
			self.shift_in = Signal()
			self.shift_out = Signal()
		
		
	def get_fragment(self):
		_shift_out = Signal()
		comb = []
		sync = []
		if self.prog_mode == "PAR":
			sync += [
				If(self.prog,
					self._shift_dat.eq(self.prog_dat),
					self._shift_cnt.eq(16)
				),
			
				If(self._shift_cnt != 0,
					self._shift_dat.eq(self._shift_dat[1:]),
					self._shift_cnt.eq(self._shift_cnt-1),
					self._ce.eq(1)
				).Else(
					self._ce.eq(0)
				)
				]
			comb += [
				self._shift_in.eq(self._shift_dat[0])
				]
		elif self.prog_mode == "SHIFT":
			comb += [
				self._ce.eq(self.shift_ce),
				self._shift_in.eq(self.shift_in)
				]
		inst = [
			Instance("SRLC16E",
				[
				("a0", self.i0),
				("a1", self.i1),
				("a2", self.i2),
				("a3", self.i3),
				("ce", self._ce),
				("d", self._shift_in)
				] , [
				("q", self._o),
				("q15",_shift_out)
				] ,
				clkport="clk",
			)
		]
		if self.prog_mode == "SHIFT":
			comb += [
				self.shift_out.eq(_shift_out)
				]
		if self.pipe:
			sync += [self.o.eq(self._o)]
		else:
			comb += [self.o.eq(self._o)]
		return Fragment(comb=comb,sync=sync,instances=inst)


class Recorder:
	def __init__(self, width, depth):
		self.width = width
		self.depth = depth
		self.depth_width = bits_for(self.depth)
		#Control
		self.rst = Signal()
		self.start = Signal()
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
				self._get_cnt.eq(0)
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
			If(self._put_cnt == self.size-1,
				self.done.eq(1)
			).Elif(self._get_cnt == self.size-1,
				self.done.eq(1)
			).Else(
				self.done.eq(0)
			)
			]
		return Fragment(comb=comb, sync=sync, memories=memories)

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