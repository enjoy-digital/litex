from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.transactions import *
from migen.flow.network import *
from migen.actorlib.sim import *
from migen.sim.generic import Simulator

def source_gen():
	for i in range(10):
		print("Sending:  " + str(i))
		yield Token("source", {"value": i})

def sink_gen():
	while True:
		t = Token("sink")
		yield t
		print("Received: " + str(t.value["value"]))

def main():
	source = SimActor(source_gen(), ("source", Source, [("value", 32)]))
	sink = SimActor(sink_gen(), ("sink", Sink, [("value", 32)]))
	g = DataFlowGraph()
	g.add_connection(source, sink)
	comp = CompositeActor(g)
	def end_simulation(s):
		s.interrupt = source.token_exchanger.done
	fragment = comp.get_fragment() + Fragment(sim=[end_simulation])
	sim = Simulator(fragment)
	sim.run()

main()
