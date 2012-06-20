from migen.flow.network import *
from migen.actorlib import structuring
from migen.actorlib.sim import *
from migen.sim.generic import Simulator
from migen.sim.icarus import Runner

pack_factor = 5

def source_gen():
	for i in range(80):
		yield Token("source", {"value": i})

def sink_gen():
	while True:
		t = Token("sink")
		yield t
		print(t.value["value"])

def main():
	base_layout = [("value", BV(32))]
	packed_layout = structuring.pack_layout(base_layout, pack_factor)
	rawbits_layout = [("value", BV(32*pack_factor))]
	
	source = ActorNode(SimActor(source_gen(), ("source", Source, base_layout)))
	sink = ActorNode(SimActor(sink_gen(), ("sink", Sink, base_layout)))
	
	# A tortuous way of passing integer tokens.
	packer = ActorNode(structuring.Pack(base_layout, pack_factor))
	to_raw = ActorNode(structuring.Cast(packed_layout, rawbits_layout))
	from_raw = ActorNode(structuring.Cast(rawbits_layout, packed_layout))
	unpacker = ActorNode(structuring.Unpack(pack_factor, base_layout))
	
	g = DataFlowGraph()
	g.add_connection(source, packer)
	g.add_connection(packer, to_raw)
	g.add_connection(to_raw, from_raw)
	g.add_connection(from_raw, unpacker)
	g.add_connection(unpacker, sink)
	comp = CompositeActor(g)
	
	fragment = comp.get_fragment()
	sim = Simulator(fragment, Runner())
	sim.run(100)

main()
