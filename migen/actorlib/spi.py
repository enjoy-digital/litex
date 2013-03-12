# Simple Processor Interface

from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.bank.description import *
from migen.flow.actor import *

# layout is a list of tuples, either:
# - (name, nbits, [reset value], [alignment bits])
# - (name, sublayout)

def _convert_layout(layout):
	r = []
	for element in layout:
		if isinstance(element[1], list):
			r.append((element[0], _convert_layout(element[1])))
		else:
			r.append((element[0], element[1]))
	return r

def _create_registers_assign(layout, target, atomic, prefix=""):
	registers = []
	assigns = []
	for element in layout:
		if isinstance(element[1], list):
			r_registers, r_assigns = _create_registers_assign(element[1],
				atomic,
				getattr(target, element[0]),
				element[0] + "_")
			registers += r_registers
			assigns += r_assigns
		else:
			name = element[0]
			nbits = element[1]
			if len(element) > 2:
				reset = element[2]
			else:
				reset = 0
			if len(element) > 3:
				alignment = element[3]
			else:
				alignment = 0
			reg = RegisterField(nbits + alignment, reset=reset, atomic_write=atomic, name=prefix + name)
			registers.append(reg)
			assigns.append(getattr(target, name).eq(reg.field.r[alignment:]))
	return registers, assigns

(MODE_EXTERNAL, MODE_SINGLE_SHOT, MODE_CONTINUOUS) = range(3)

class SingleGenerator(Actor):
	def __init__(self, layout, mode):
		self._mode = mode
		Actor.__init__(self, ("source", Source, _convert_layout(layout)))
		self._registers, self._assigns = _create_registers_assign(layout,
			self.token("source"), self._mode != MODE_SINGLE_SHOT)
		if mode == MODE_EXTERNAL:
			self.trigger = Signal()
		elif mode == MODE_SINGLE_SHOT:
			shoot = RegisterRaw()
			self._registers.insert(0, shoot)
			self.trigger = shoot.re
		elif mode == MODE_CONTINUOUS:
			enable = RegisterField()
			self._registers.insert(0, enable)
			self.trigger = enable.field.r
		else:
			raise ValueError
	
	def get_registers(self):
		return self._registers
	
	def get_fragment(self):
		stb = self.endpoints["source"].stb
		ack = self.endpoints["source"].ack
		comb = [
			self.busy.eq(stb)
		]
		stmts = [stb.eq(self.trigger)] + self._assigns
		sync = [If(ack | ~stb, *stmts)]
		return Fragment(comb, sync)

class Collector(Actor):
	def __init__(self, layout, depth=1024):
		Actor.__init__(self, ("sink", Sink, layout))
		self._depth = depth
		self._dw = sum(len(s) for s in self.token("sink").flatten())
		
		self._r_wa = RegisterField(bits_for(self._depth-1), READ_WRITE, READ_WRITE)
		self._r_wc = RegisterField(bits_for(self._depth), READ_WRITE, READ_WRITE, atomic_write=True)
		self._r_ra = RegisterField(bits_for(self._depth-1), READ_WRITE, READ_ONLY)
		self._r_rd = RegisterField(self._dw, READ_ONLY, WRITE_ONLY)
	
	def get_registers(self):
		return [self._r_wa, self._r_wc, self._r_ra, self._r_rd]
	
	def get_fragment(self):
		mem = Memory(self._dw, self._depth)
		wp = mem.get_port(write_capable=True)
		rp = mem.get_port()
		
		comb = [
			If(self._r_wc.field.r != 0,
				self.endpoints["sink"].ack.eq(1),
				If(self.endpoints["sink"].stb,
					self._r_wa.field.we.eq(1),
					self._r_wc.field.we.eq(1),
					wp.we.eq(1)
				)
			),
			self._r_wa.field.w.eq(self._r_wa.field.r + 1),
			self._r_wc.field.w.eq(self._r_wc.field.r - 1),
			
			wp.adr.eq(self._r_wa.field.r),
			wp.dat_w.eq(Cat(*self.token("sink").flatten())),
			
			rp.adr.eq(self._r_ra.field.r),
			self._r_rd.field.w.eq(rp.dat_r)
		]
		
		return Fragment(comb, specials={mem})
