from random import Random

from migen.fhdl.structure import *
from migen.bus.asmibus import *
from migen.sim.generic import Simulator, TopLevel
from migen.sim.icarus import Runner

from milkymist import asmicon
from milkymist.asmicon.bankmachine import _AddressSlicer, _Selector, _Buffer

from common import SlotsLogger

sdram_geom = asmicon.GeomSettings(
	bank_a=2,
	row_a=13,
	col_a=10
)

def my_generator(dt, offset):
	for t in range(dt):
		yield None
	for x in range(10):
		t = TRead(x + offset)
		yield t

class Selector:
	def __init__(self, slicer, bankn, slots):
		self.selector = _Selector(slicer, bankn, slots)
		self.buf = _Buffer(self.selector)
		self.queue = []
		self.prng = Random(876)
	
	def do_simulation(self, s):
		if self.prng.randrange(0, 5):
			s.wr(self.buf.ack, 1)
		else:
			s.wr(self.buf.ack, 0)
		if s.rd(self.buf.stb) and s.rd(self.buf.ack):
			tag = s.rd(self.buf.tag)
			self.queue.append(tag)
			print("==> SELECTED: " + str(tag))
		print("")
	
	def get_fragment(self):
		return self.selector.get_fragment() + \
			self.buf.get_fragment() + \
			Fragment(sim=[self.do_simulation])

class Completer:
	def __init__(self, hub, queue):
		self.hub = hub
		self.queue = queue
	
	def do_simulation(self, s):
		if self.queue:
			tag = self.queue.pop()
			s.wr(self.hub.call, 1)
			s.wr(self.hub.tag_call, tag)
		else:
			s.wr(self.hub.call, 0)
		
	def get_fragment(self):
		return Fragment(sim=[self.do_simulation])

def main():
	hub = Hub(12, 128, 8)
	initiators = [Initiator(hub.get_port(), my_generator(0, 2200*(i//6)+i*10))
		for i in range(8)]
	hub.finalize()
	
	slots = hub.get_slots()
	slicer = _AddressSlicer(sdram_geom, 2)
	logger = SlotsLogger(slicer, slots)
	selector = Selector(slicer, 0, slots)
	completer = Completer(hub, selector.queue)
	
	def end_simulation(s):
		s.interrupt = all([i.done for i in initiators])
	
	fragment = hub.get_fragment() + sum([i.get_fragment() for i in initiators], Fragment()) + \
		logger.get_fragment() + selector.get_fragment() + completer.get_fragment() + \
		Fragment(sim=[end_simulation])
	sim = Simulator(fragment, Runner(), TopLevel("my.vcd"))
	sim.run()

main()
