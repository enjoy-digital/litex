from itertools import count

import networkx as nx
import matplotlib.pyplot as plt

from migen.flow.network import *
from migen.flow.transactions import *
from migen.actorlib import structuring
from migen.actorlib.sim import *
from migen.sim.generic import Simulator
from migen.flow import perftools

pack_factor = 5

def source_gen():
	for i in count(0):
		yield Token("source", {"value": i})

def sink_gen():
	while True:
		t = Token("sink")
		yield t
		print(t.value["value"])

def main():
	base_layout = [("value", 32)]
	packed_layout = structuring.pack_layout(base_layout, pack_factor)
	rawbits_layout = [("value", 32*pack_factor)]
	
	source = SimActor(source_gen(), ("source", Source, base_layout))
	sink = SimActor(sink_gen(), ("sink", Sink, base_layout))
	
	# A tortuous way of passing integer tokens.
	packer = structuring.Pack(base_layout, pack_factor)
	to_raw = structuring.Cast(packed_layout, rawbits_layout)
	from_raw = structuring.Cast(rawbits_layout, packed_layout)
	unpacker = structuring.Unpack(pack_factor, base_layout)
	
	g = DataFlowGraph()
	g.add_connection(source, packer)
	g.add_connection(packer, to_raw)
	g.add_connection(to_raw, from_raw)
	g.add_connection(from_raw, unpacker)
	g.add_connection(unpacker, sink)
	comp = CompositeActor(g)
	reporter = perftools.DFGReporter(g)
	
	fragment = comp.get_fragment() + reporter.get_fragment()
	sim = Simulator(fragment)
	sim.run(1000)
	
	g_layout = nx.spectral_layout(g)
	nx.draw(g, g_layout)
	nx.draw_networkx_edge_labels(g, g_layout, reporter.get_edge_labels())
	plt.show()


main()
