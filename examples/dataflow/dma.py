from random import Random

from migen.flow.ala import *
from migen.flow.network import *
from migen.actorlib import dma_wishbone, dma_asmi
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
	def _end_simulation(s):
		s.interrupt = end_simulation(s)
	fragment = efragment \
		+ peripheral.get_fragment() \
		+ tap.get_fragment() \
		+ interconnect.get_fragment() \
		+ Fragment(sim=[_end_simulation])
	sim = Simulator(fragment, Runner())
	sim.run()

def asmi_sim(efragment, hub, end_simulation):
	def _end_simulation(s):
		s.interrupt = end_simulation(s)
	peripheral = asmibus.Target(hub, MyModelASMI())
	tap = asmibus.Tap(hub)
	def _end_simulation(s):
		s.interrupt = end_simulation(s)
	fragment = efragment \
		+ peripheral.get_fragment() \
		+ tap.get_fragment() \
		+ Fragment(sim=[_end_simulation])
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
	
	wishbone_sim(comp.get_fragment(), reader,
		lambda s: adrgen.done and not s.rd(comp.busy))

def test_wb_writer():
	print("*** Testing Wishbone writer")
	trgen = SimActor(trgen_gen(), ("address_data", Source, [("a", BV(30)), ("d", BV(32))]))
	writer = dma_wishbone.Writer()
	g = DataFlowGraph()
	g.add_connection(trgen, writer)
	comp = CompositeActor(g)
	
	wishbone_sim(comp.get_fragment(), writer,
		lambda s: trgen.done and not s.rd(comp.busy))

def test_asmi_seqreader():
	print("*** Testing ASMI sequential reader")
	
	hub = asmibus.Hub(32, 32)
	port = hub.get_port()
	hub.finalize()
	
	adrgen = SimActor(adrgen_gen(), ("address", Source, [("a", BV(32))]))
	reader = dma_asmi.SequentialReader(port)
	dumper = SimActor(dumper_gen(), ("data", Sink, [("d", BV(32))]))
	g = DataFlowGraph()
	g.add_connection(adrgen, reader)
	g.add_connection(reader, dumper)
	comp = CompositeActor(g)
	
	asmi_sim(hub.get_fragment() + comp.get_fragment(), hub,
		lambda s: adrgen.done and not s.rd(comp.busy))

test_wb_reader()
test_wb_writer()
test_asmi_seqreader()
