from migen.flow.network import *
from migen.actorlib.sim import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.uio.ioo import UnifiedIOSimulation
from migen.pytholite.transel import Register
from migen.pytholite.compiler import make_pytholite
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner
from migen.fhdl import verilog

layout = [("r", BV(32))]

def gen():
	ds = Register(32)
	for i in range(5):
		# NB: busname is optional when only one bus is configured
		r = TRead(i, busname="wb")
		yield r
		ds.store = r.data
		yield Token("result", {"r": ds})

class Dumper(SimActor):
	def __init__(self):
		def dumper_gen():
			while True:
				t = Token("result")
				yield t
				print(t.value["r"])
		super().__init__(dumper_gen(),
			("result", Sink, layout))

class SlaveModel(wishbone.TargetModel):
	def read(self, address):
		return address + 4

def run_sim(ng):
	g = DataFlowGraph()
	d = Dumper()
	g.add_connection(ActorNode(ng), ActorNode(d))
	
	slave = wishbone.Target(SlaveModel())
	intercon = wishbone.InterconnectPointToPoint(ng.buses["wb"], slave.bus)
	
	c = CompositeActor(g)
	fragment = slave.get_fragment() + intercon.get_fragment() + c.get_fragment()
	
	sim = Simulator(fragment, Runner())
	sim.run(30)
	del sim

def main():
	print("Simulating native Python:")
	ng_native = UnifiedIOSimulation(gen(), 
		dataflow=[("result", Source, layout)],
		buses={"wb": wishbone.Interface()})
	run_sim(ng_native)
	
	print("Simulating Pytholite:")
	ng_pytholite = make_pytholite(gen,
		dataflow=[("result", Source, layout)],
		buses={"wb": wishbone.Interface()})
	run_sim(ng_pytholite)
	
	print("Converting Pytholite to Verilog:")
	print(verilog.convert(ng_pytholite.get_fragment()))

main()
