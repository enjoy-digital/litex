from random import Random

from migen.fhdl.module import Module
from migen.flow.network import *
from migen.flow.transactions import *
from migen.actorlib import dma_wishbone, dma_asmi
from migen.actorlib.sim import *
from migen.bus import wishbone, asmibus
from migen.sim.generic import Simulator

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
		print("Address:  " + hex(i))
		yield Token("address", {"a": i})

class SimAdrGen(SimActor):
	def __init__(self, nbits):
		self.address = Source([("a", nbits)])
		SimActor.__init__(self, adrgen_gen())

def dumper_gen():
	while True:
		t = Token("data", idle_wait=True)
		yield t
		print("Received: " + hex(t.value["d"]))

class SimDumper(SimActor):
	def __init__(self):
		self.data = Sink([("d", 32)])
		SimActor.__init__(self, dumper_gen())		

def trgen_gen():
	for i in range(10):
		a = i
		d = i+10
		print("Address: " + hex(a) + " Data: " + hex(d))
		yield Token("address_data", {"a": a, "d": d})

class SimTrGen(SimActor):
	def __init__(self, a_nbits):
		self.address_data = Source([("a", a_nbits), ("d", 32)])
		SimActor.__init__(self, trgen_gen())

class TBWishbone(Module):
	def __init__(self, master):
		self.submodules.peripheral = wishbone.Target(MyModelWB())
		self.submodules.tap = wishbone.Tap(self.peripheral.bus)
		self.submodules.interconnect = wishbone.InterconnectPointToPoint(master.bus,
		  self.peripheral.bus)

class TBWishboneReader(TBWishbone):
	def __init__(self):
		self.adrgen = SimAdrGen(30)
		self.reader = dma_wishbone.Reader()
		self.dumper = SimDumper()
		g = DataFlowGraph()
		g.add_connection(self.adrgen, self.reader)
		g.add_connection(self.reader, self.dumper)
		self.submodules.comp = CompositeActor(g)
		TBWishbone.__init__(self, self.reader)

	def do_simulation(self, s):
		s.interrupt = self.adrgen.token_exchanger.done and not s.rd(self.comp.busy)

class TBWishboneWriter(TBWishbone):
	def __init__(self):
		self.trgen = SimTrGen(30)
		self.writer = dma_wishbone.Writer()
		g = DataFlowGraph()
		g.add_connection(self.trgen, self.writer)
		self.submodules.comp = CompositeActor(g)
		TBWishbone.__init__(self, self.writer)

	def do_simulation(self, s):
		s.interrupt = self.trgen.token_exchanger.done and not s.rd(self.comp.busy)

class TBAsmi(Module):
	def __init__(self, nslots):
		self.submodules.hub = asmibus.Hub(32, 32)
		self.port = self.hub.get_port(nslots)
		self.hub.finalize()

		self.submodules.peripheral = asmibus.Target(MyModelASMI(), self.hub)
		self.submodules.tap = asmibus.Tap(self.hub)

class TBAsmiReader(TBAsmi):
	def __init__(self, nslots):
		TBAsmi.__init__(self, nslots)
		
		self.adrgen = SimAdrGen(32)
		self.reader = dma_asmi.Reader(self.port)
		self.dumper = SimDumper()
		g = DataFlowGraph()
		g.add_connection(self.adrgen, self.reader)
		g.add_connection(self.reader, self.dumper)
		self.submodules.comp = CompositeActor(g)

	def do_simulation(self, s):
		s.interrupt = self.adrgen.token_exchanger.done and not s.rd(self.comp.busy)

class TBAsmiWriter(TBAsmi):
	def __init__(self, nslots):
		TBAsmi.__init__(self, nslots)
		
		self.trgen = SimTrGen(32)
		self.writer = dma_asmi.Writer(self.port)
		g = DataFlowGraph()
		g.add_connection(self.trgen, self.writer)
		self.submodules.comp = CompositeActor(g)
		
	def do_simulation(self, s):
		s.interrupt = self.trgen.token_exchanger.done and not s.rd(self.comp.busy)

def test_wb_reader():
	print("*** Testing Wishbone reader")
	Simulator(TBWishboneReader()).run()

def test_wb_writer():
	print("*** Testing Wishbone writer")
	Simulator(TBWishboneWriter()).run()

def test_asmi_reader(nslots):
	print("*** Testing ASMI reader (nslots={})".format(nslots))
	Simulator(TBAsmiReader(nslots)).run()

def test_asmi_writer(nslots):
	print("*** Testing ASMI writer (nslots={})".format(nslots))
	Simulator(TBAsmiWriter(nslots)).run()

test_wb_reader()
test_wb_writer()
test_asmi_reader(1)
test_asmi_reader(2)
test_asmi_writer(1)
test_asmi_writer(2)
