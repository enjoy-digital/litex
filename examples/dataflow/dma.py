from random import Random

from migen.fhdl import verilog
from migen.flow.ala import *
from migen.flow.network import *
from migen.actorlib import dma_wishbone
from migen.actorlib.sim import *
from migen.bus import wishbone, asmibus
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

class MyModel:
	def read(self, address):
		return address + 4

class MyModelWB(MyModel, wishbone.TargetModel):
	def __init__(self):
		self.prng = Random(763627)

	def can_ack(self, bus):
		return self.prng.randrange(0, 2)

class MyModelASMI(MyModel, asmibus.TargetModel):
	pass

def adrgen_gen():
	for i in range(10):
		print("Address:  " + str(i))
		yield Token("address", {"a": i})

def dumper_gen():
	while True:
		t = Token("data")
		yield t
		print("Received: " + str(t.value["d"]))

def trgen_gen():
	for i in range(10):
		a = i
		d = i+10
		print("Address: " + str(a) + " Data: " + str(d))
		yield Token("address_data", {"a": a, "d": d})

def wishbone_sim(efragment, master, end_simulation):
	peripheral = wishbone.Target(MyModelWB())
	tap = wishbone.Tap(peripheral.bus)
	interconnect = wishbone.InterconnectPointToPoint(master.bus, peripheral.bus)

	fragment = efragment \
		+ peripheral.get_fragment() \
		+ tap.get_fragment() \
		+ interconnect.get_fragment() \
		+ Fragment(sim=[end_simulation])
	
	sim = Simulator(fragment, Runner())
	sim.run()

def test_wb_reader():
	print("*** Testing Wishbone reader")
	adrgen = SimActor(adrgen_gen(), ("address", Source, [("a", BV(30))]))
	reader = dma_wishbone.Reader()
	dumper = SimActor(dumper_gen(), ("data", Sink, [("d", BV(32))]))
	g = DataFlowGraph()
	g.add_connection(adrgen, reader)
	g.add_connection(reader, dumper)
	comp = CompositeActor(g)
	
	def end_simulation(s):
		s.interrupt = adrgen.done and not s.rd(comp.busy)
	wishbone_sim(comp.get_fragment(), reader, end_simulation)

def test_wb_writer():
	print("*** Testing Wishbone writer")
	trgen = SimActor(trgen_gen(), ("address_data", Source, [("a", BV(30)), ("d", BV(32))]))
	writer = dma_wishbone.Writer()
	g = DataFlowGraph()
	g.add_connection(trgen, writer)
	comp = CompositeActor(g)
	
	def end_simulation(s):
		s.interrupt = trgen.done and not s.rd(comp.busy)
	wishbone_sim(comp.get_fragment(), writer, end_simulation)

test_wb_reader()
test_wb_writer()
