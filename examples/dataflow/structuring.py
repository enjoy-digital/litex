from migen.flow.network import *
from migen.actorlib import structuring
from migen.actorlib.sim import *
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

pack_factor = 5

def source_gen():
	for i in range(80):
		#print("==> " + str(i))
		yield Token("source", {"value": i})

def sink_gen():
	while True:
		t = Token("sink")
		yield t
		print(t.value["value"])

def main():
	base_layout = [("value", BV(32))]
	
	source = ActorNode(SimActor(source_gen(), ("source", Source, base_layout)))
	packer = ActorNode(structuring.Pack(base_layout, pack_factor))
	unpacker = ActorNode(structuring.Unpack(pack_factor, base_layout))
	sink = ActorNode(SimActor(sink_gen(), ("sink", Sink, base_layout)))
	
	g = DataFlowGraph()
	g.add_connection(source, packer)
	g.add_connection(packer, unpacker)
	g.add_connection(unpacker, sink)
	comp = CompositeActor(g)
	
	fragment = comp.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(100)

main()
