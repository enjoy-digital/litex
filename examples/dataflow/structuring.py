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
base_layout = [("value", 32)]
packed_layout = structuring.pack_layout(base_layout, pack_factor)
rawbits_layout = [("value", 32*pack_factor)]

def source_gen():
	for i in count(0):
		yield Token("source", {"value": i})

class SimSource(SimActor):
	def __init__(self):
		self.source = Source(base_layout)
		SimActor.__init__(self, source_gen())

def sink_gen():
	while True:
		t = Token("sink")
		yield t
		print(t.value["value"])

class SimSink(SimActor):
	def __init__(self):
		self.sink = Sink(base_layout)
		SimActor.__init__(self, sink_gen())

class TB(Module):
	def __init__(self):
		source = SimSource()
		sink = SimSink()
		
		# A tortuous way of passing integer tokens.
		packer = structuring.Pack(base_layout, pack_factor)
		to_raw = structuring.Cast(packed_layout, rawbits_layout)
		from_raw = structuring.Cast(rawbits_layout, packed_layout)
		unpacker = structuring.Unpack(pack_factor, base_layout)
		
		self.g = DataFlowGraph()
		self.g.add_connection(source, packer)
		self.g.add_connection(packer, to_raw)
		self.g.add_connection(to_raw, from_raw)
		self.g.add_connection(from_raw, unpacker)
		self.g.add_connection(unpacker, sink)
		self.submodules.comp = CompositeActor(self.g)
		self.submodules.reporter = perftools.DFGReporter(self.g)

def main():
	tb = TB()
	sim = Simulator(tb).run(1000)
	
	g_layout = nx.spectral_layout(tb.g)
	nx.draw(tb.g, g_layout)
	nx.draw_networkx_edge_labels(tb.g, g_layout, tb.reporter.get_edge_labels())
	plt.show()

main()
