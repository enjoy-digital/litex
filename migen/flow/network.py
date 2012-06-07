import networkx as nx

from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.misc import optree

class CompositeActor(Actor):
	def __init__(self, dfg): # TODO: endpoints
		self.dfg = dfg
		Actor.__init__(self)
	
	def get_fragment(self):
		this_fragments = [get_conn_fragment(x[0].endpoints[x[2]["source"]], x[1].endpoints[x[2]["sink"]])
			for x in self.dfg.edges(data=True)]
		this = sum(this_fragments, Fragment())
		others = sum([node.get_fragment() for node in self.dfg], Fragment())
		busy = Fragment([self.busy.eq(optree("|", [node.busy for node in self.dfg]))])
		return this + others + busy

def add_connection(dfg, source_node, sink_node, source_ep=None, sink_ep=None):
	if source_ep is None:
		source_eps = source_node.sources()
		assert(len(source_eps) == 1)
		source_ep = source_eps[0]
	if sink_ep is None:
		sink_eps = sink_node.sinks()
		assert(len(sink_eps) == 1)
		sink_ep = sink_eps[0]
	dfg.add_edge(source_node, sink_node, source=source_ep, sink=sink_ep)
