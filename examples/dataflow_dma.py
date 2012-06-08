from random import Random

from migen.fhdl import verilog
from migen.flow.ala import *
from migen.flow.network import *
from migen.actorlib import dma_wishbone
from migen.actorlib.sim import *
from migen.bus import wishbone
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

class MyPeripheral:
	def __init__(self):
		self.bus = wishbone.Interface()
		self.ack_en = Signal()
		self.prng = Random(763627)

	def do_simulation(self, s):
		# Only authorize acks on certain cycles to simulate variable latency.
		s.wr(self.ack_en, self.prng.randrange(0, 2))

	def get_fragment(self):
		comb = [
			self.bus.ack.eq(self.bus.cyc & self.bus.stb & self.ack_en),
			self.bus.dat_r.eq(self.bus.adr + 4)
		]
		return Fragment(comb, sim=[self.do_simulation])

def adrgen_gen():
	for i in range(10):
		print("Address:  " + str(i))
		yield Token("address", {"a": i})

def dumper_gen():
	while True:
		t = Token("data")
		yield t
		print("Received: " + str(t.value["d"]))

def test_reader():
	print("*** Testing reader")
	adrgen = SimActor(adrgen_gen(), ("address", Source, [("a", BV(30))]))
	reader = dma_wishbone.Reader()
	dumper = SimActor(dumper_gen(), ("data", Sink, [("d", BV(32))]))
	g = DataFlowGraph()
	g.add_connection(adrgen, reader)
	g.add_connection(reader, dumper)
	comp = CompositeActor(g)
	
	peripheral = MyPeripheral()
	interconnect = wishbone.InterconnectPointToPoint(reader.bus, peripheral.bus)
	
	def end_simulation(s):
		s.interrupt = adrgen.done and not s.rd(comp.busy)
	
	fragment = comp.get_fragment() \
		+ peripheral.get_fragment() \
		+ interconnect.get_fragment() \
		+ Fragment(sim=[end_simulation])
	
	sim = Simulator(fragment, Runner())
	sim.run()

def trgen_gen():
	for i in range(10):
		a = i
		d = i+10
		print("Address: " + str(a) + " Data: " + str(d))
		yield Token("address_data", {"a": a, "d": d})
	
def test_writer():
	print("*** Testing writer")
	trgen = SimActor(trgen_gen(), ("address_data", Source, [("a", BV(30)), ("d", BV(32))]))
	writer = dma_wishbone.Writer()
	g = DataFlowGraph()
	g.add_connection(trgen, writer)
	comp = CompositeActor(g)
	
	peripheral = MyPeripheral()
	tap = wishbone.Tap(peripheral.bus)
	interconnect = wishbone.InterconnectPointToPoint(writer.bus, peripheral.bus)
	
	def end_simulation(s):
		s.interrupt = trgen.done and not s.rd(comp.busy)
	
	fragment = comp.get_fragment() \
		+ peripheral.get_fragment() \
		+ tap.get_fragment() \
		+ interconnect.get_fragment() \
		+ Fragment(sim=[end_simulation])
	
	sim = Simulator(fragment, Runner())
	sim.run()

test_reader()
test_writer()
