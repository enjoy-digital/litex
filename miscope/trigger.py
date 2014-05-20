from migen.fhdl.std import *
from migen.fhdl.specials import Memory
from migen.bank.description import *

from miscope.std import *

class Term(Module, AutoCSR):
	def __init__(self, width):
		self.width = width

		self.sink = rec_dat(width)
		self.source = rec_hit()

		self._r_trig = CSRStorage(width)
		self._r_mask = CSRStorage(width)

	###

		trig = self._r_trig.storage
		mask = self._r_mask.storage
		dat = self.sink.dat
		hit = self.source.hit

		self.comb +=[
			hit.eq((dat & mask) == trig),
			self.source.stb.eq(self.sink.stb)
		]

class RangeDetector(Module, AutoCSR):
	def __init__(self, width):
		self.width = width

		self.sink = rec_dat(width)
		self.source = rec_hit()

		self._r_low = CSRStorage(width)
		self._r_high = CSRStorage(width)

	###

		low = self._r_low.storage
		high = self._r_high.storage
		dat = self.sink.dat
		hit = self.source.hit

		self.comb +=[
			hit.eq((dat >= low) & (dat <= high)),
			self.source.stb.eq(self.sink.stb)
		]


class EdgeDetector(Module, AutoCSR):
	def __init__(self, width):
		self.width = width
		
		self.sink = rec_dat(width)
		self.source = rec_hit()

		self._r_rising_mask = CSRStorage(width)
		self._r_falling_mask = CSRStorage(width)
		self._r_both_mask = CSRStorage(width)

	###

		rising_mask = self._r_rising_mask.storage
		falling_mask = self._r_falling_mask.storage
		both_mask = self._r_both_mask.storage

		dat = self.sink.dat
		dat_d = Signal(width)
		rising_hit = Signal()
		falling_hit = Signal()
		both_hit = Signal()
		hit = self.source.hit

		self.sync += dat_d.eq(dat)

		self.comb +=[
			rising_hit.eq(rising_mask & dat & ~dat_d),
			falling_hit.eq(rising_mask & ~dat & dat_d),
			both_hit.eq((both_mask & dat) != (both_mask & dat_d)),
			hit.eq(rising_hit | falling_hit | both_hit),
			self.source.stb.eq(self.sink.stb)
		]

class Sum(Module, AutoCSR):
	def __init__(self, ports=4):
		
		self.sinks = [rec_hit() for p in range(ports)]
		self.source = rec_hit()
		
		self._r_prog_we = CSRStorage()
		self._r_prog_adr = CSRStorage(ports) #FIXME
		self._r_prog_dat = CSRStorage()

		mem = Memory(1, 2**ports)
		lut_port = mem.get_port()
		prog_port = mem.get_port(write_capable=True)

		self.specials += mem, lut_port, prog_port

		###

		# Lut prog
		self.comb +=[
			prog_port.we.eq(self._r_prog_we.storage),
			prog_port.adr.eq(self._r_prog_adr.storage),
			prog_port.dat_w.eq(self._r_prog_dat.storage)
		]

		# Lut read
		for i, sink in enumerate(self.sinks):
			self.comb += lut_port.adr[i].eq(sink.hit)

		# Drive source
		self.comb +=[
			self.source.stb.eq(optree("&", [sink.stb for sink in self.sinks])),
			self.source.hit.eq(lut_port.dat_r),
		]


class Trigger(Module, AutoCSR):
	def __init__(self, width, ports):
		self.width = width
		self.ports = ports
		
		self.submodules.sum = Sum(len(ports))

		# FIXME : when self.submodules +=  is used, 
		# get_csrs() is not called
		for i, port in enumerate(ports):
			tmp = "self.submodules.port"+str(i)+" = port"
			exec(tmp)

		self.sink   = rec_dat(width)
		self.source = self.sum.source
		self.busy = Signal()

		###
		for i, port in enumerate(ports):
			self.comb +=[
				self.sink.connect(port.sink),
				port.source.connect(self.sum.sinks[i])
			]