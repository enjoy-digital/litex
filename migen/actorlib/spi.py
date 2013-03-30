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

def _create_csrs_assign(layout, target, atomic, prefix=""):
	csrs = []
	assigns = []
	for element in layout:
		if isinstance(element[1], list):
			r_csrs, r_assigns = _create_csrs_assign(element[1],
				atomic,
				getattr(target, element[0]),
				element[0] + "_")
			csrs += r_csrs
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
			reg = CSRStorage(nbits + alignment, reset=reset, atomic_write=atomic, name=prefix + name)
			csrs.append(reg)
			assigns.append(getattr(target, name).eq(reg.storage[alignment:]))
	return csrs, assigns

(MODE_EXTERNAL, MODE_SINGLE_SHOT, MODE_CONTINUOUS) = range(3)

class SingleGenerator(Actor):
	def __init__(self, layout, mode):
		self._mode = mode
		Actor.__init__(self, ("source", Source, _convert_layout(layout)))
		self._csrs, self._assigns = _create_csrs_assign(layout,
			self.token("source"), self._mode != MODE_SINGLE_SHOT)
		if mode == MODE_EXTERNAL:
			self.trigger = Signal()
		elif mode == MODE_SINGLE_SHOT:
			shoot = CSR()
			self._csrs.insert(0, shoot)
			self.trigger = shoot.re
		elif mode == MODE_CONTINUOUS:
			enable = CSRStorage()
			self._csrs.insert(0, enable)
			self.trigger = enable.storage
		else:
			raise ValueError
	
	def get_csrs(self):
		return self._csrs
	
	def get_fragment(self):
		stb = self.endpoints["source"].stb
		ack = self.endpoints["source"].ack
		comb = [
			self.busy.eq(stb)
		]
		stmts = [stb.eq(self.trigger)] + self._assigns
		sync = [If(ack | ~stb, *stmts)]
		return Fragment(comb, sync)

class Collector(Actor, AutoCSR):
	def __init__(self, layout, depth=1024):
		Actor.__init__(self, ("sink", Sink, layout))
		self._depth = depth
		self._dw = sum(len(s) for s in self.token("sink").flatten())
		
		self._r_wa = CSRStorage(bits_for(self._depth-1), write_from_dev=True)
		self._r_wc = CSRStorage(bits_for(self._depth), write_from_dev=True, atomic_write=True)
		self._r_ra = CSRStorage(bits_for(self._depth-1))
		self._r_rd = CSRStatus(self._dw)
	
	def get_fragment(self):
		mem = Memory(self._dw, self._depth)
		wp = mem.get_port(write_capable=True)
		rp = mem.get_port()
		
		comb = [
			If(self._r_wc.r != 0,
				self.endpoints["sink"].ack.eq(1),
				If(self.endpoints["sink"].stb,
					self._r_wa.we.eq(1),
					self._r_wc.we.eq(1),
					wp.we.eq(1)
				)
			),
			self._r_wa.dat_w.eq(self._r_wa.storage + 1),
			self._r_wc.dat_w.eq(self._r_wc.storage - 1),
			
			wp.adr.eq(self._r_wa.storage),
			wp.dat_w.eq(Cat(*self.token("sink").flatten())),
			
			rp.adr.eq(self._r_ra.storage),
			self._r_rd.status.eq(rp.dat_r)
		]
		
		return Fragment(comb, specials={mem})
