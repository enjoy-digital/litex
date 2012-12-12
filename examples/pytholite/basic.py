from migen.flow.network import *
from migen.actorlib.sim import *
from migen.pytholite.compiler import make_pytholite
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner
from migen.fhdl import verilog

layout = [("r", 32)]

def number_gen():
	for i in range(10):
		yield Token("result", {"r": i})

def run_sim(ng):
	g = DataFlowGraph()
	d = Dumper(layout)
	g.add_connection(ng, d)
	
	c = CompositeActor(g)
	fragment = c.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(30)
	del sim

def main():
	print("Simulating native Python:")
	ng_native = SimActor(number_gen(), ("result", Source, layout))
	run_sim(ng_native)
	
	print("Simulating Pytholite:")
	ng_pytholite = make_pytholite(number_gen, dataflow=[("result", Source, layout)])
	run_sim(ng_pytholite)
	
	print("Converting Pytholite to Verilog:")
	print(verilog.convert(ng_pytholite.get_fragment()))

main()
