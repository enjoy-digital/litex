from migen.flow.network import *
from migen.actorlib.sim import *
from migen.pytholite.compiler import make_pytholite
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

layout = [("r", BV(32))]

def number_gen():
	for i in range(10):
		yield Token("result", {"r": i})

class Dumper(SimActor):
	def __init__(self):
		def dumper_gen():
			while True:
				t = Token("result")
				yield t
				print(t.value["r"])
		super().__init__(dumper_gen(),
			("result", Sink, layout))

def run_sim(ng):
	g = DataFlowGraph()
	d = Dumper()
	g.add_connection(ActorNode(ng), ActorNode(d))
	
	c = CompositeActor(g)
	fragment = c.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(30)
	del sim

def main():
	print("Simulating Pytholite:")
	ng_pytholite = make_pytholite(number_gen, dataflow=[("result", Source, layout)])
	run_sim(ng_pytholite)
	
	print("Simulating native Python:")
	ng_native = SimActor(number_gen(), ("result", Source, layout))
	run_sim(ng_native)

main()
