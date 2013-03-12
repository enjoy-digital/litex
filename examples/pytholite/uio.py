from migen.flow.network import *
from migen.flow.transactions import *
from migen.actorlib.sim import Dumper
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.uio.ioo import UnifiedIOSimulation
from migen.pytholite.transel import Register
from migen.pytholite.compiler import make_pytholite
from migen.sim.generic import Simulator
from migen.fhdl.module import Module
from migen.fhdl.specials import Memory
from migen.fhdl import verilog

layout = [("r", 32)]

def gen():
	ds = Register(32)
	for i in range(3):
		r = TRead(i, busname="mem")
		yield r
		ds.store = r.data
		yield Token("result", {"r": ds})
	for i in range(5):
		r = TRead(i, busname="wb")
		yield r
		ds.store = r.data
		yield Token("result", {"r": ds})

class SlaveModel(wishbone.TargetModel):
	def read(self, address):
		return address + 4

class TestBench(Module):
	def __init__(self, ng):
		g = DataFlowGraph()
		d = Dumper(layout)
		g.add_connection(ng, d)
		
		self.submodules.slave = wishbone.Target(SlaveModel())
		self.submodules.intercon = wishbone.InterconnectPointToPoint(ng.buses["wb"], self.slave.bus)
		self.submodules.ca = CompositeActor(g)

def run_sim(ng):
	sim = Simulator(TestBench(ng))
	sim.run(50)
	del sim

def main():
	mem = Memory(32, 3, init=[42, 37, 81])
	dataflow = [("result", Source, layout)]
	buses = {
		"wb":	wishbone.Interface(),
		"mem":	mem
	}
	
	print("Simulating native Python:")
	ng_native = UnifiedIOSimulation(gen(), 
		dataflow=dataflow,
		buses=buses)
	run_sim(ng_native)
	
	print("Simulating Pytholite:")
	ng_pytholite = make_pytholite(gen,
		dataflow=dataflow,
		buses=buses)
	run_sim(ng_pytholite)
	
	print("Converting Pytholite to Verilog:")
	print(verilog.convert(ng_pytholite.get_fragment()))

main()
