from migen.flow.network import *
from migen.flow.transactions import *
from migen.actorlib.sim import Dumper
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.genlib.ioo import UnifiedIOSimulation
from migen.pytholite.transel import Register
from migen.pytholite.compiler import Pytholite
from migen.sim.generic import run_simulation
from migen.fhdl.std import *
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
		self.submodules.intercon = wishbone.InterconnectPointToPoint(ng.wb, self.slave.bus)
		self.submodules.ca = CompositeActor(g)

def run_ng_sim(ng):
	run_simulation(TestBench(ng), ncycles=50)

def add_interfaces(obj):
	obj.result = Source(layout)
	obj.wb = wishbone.Interface()
	obj.mem = Memory(32, 3, init=[42, 37, 81])
	obj.finalize()

def main():
	print("Simulating native Python:")
	ng_native = UnifiedIOSimulation(gen())
	add_interfaces(ng_native)
	run_ng_sim(ng_native)

	print("Simulating Pytholite:")
	ng_pytholite = Pytholite(gen)
	add_interfaces(ng_pytholite)
	run_ng_sim(ng_pytholite)

	print("Converting Pytholite to Verilog:")
	ng_pytholite = Pytholite(gen)
	add_interfaces(ng_pytholite)
	print(verilog.convert(ng_pytholite))

main()
