import networkx as nx

from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.misc import optree

class CompositeActor(Actor):
	def __init__(self, dfg):
		self.dfg = dfg
		# Internal unconnected endpoints become our endpoints. Determine them.
		our_endpoints = []
		for node in self.dfg:
			endpoints = set(node.endpoints)
			for u, v, d in self.dfg.in_edges([node], data=True):
				endpoints.remove(d['sink'])
			for u, v, d in self.dfg.out_edges([node], data=True):
				endpoints.remove(d['source'])
			our_endpoints += list(endpoints)
		Actor.__init__(self,
			SchedulingModel(SchedulingModel.DYNAMIC),
			endpoints=our_endpoints)
	
	def get_control_fragment(self):
		this = sum([get_conn_control_fragment(x[2]['source'], x[2]['sink'])
			for x in self.dfg.edges(data=True)], Fragment())
		others = sum([node.get_control_fragment() for node in self.dfg], Fragment())
		busy = Fragment([self.busy.eq(optree('|', [node.busy for node in self.dfg]))])
		return this + others + busy
	
	def get_process_fragment(self):
		this = sum([get_conn_process_fragment(x[2]['source'], x[2]['sink'])
			for x in self.dfg.edges(data=True)], Fragment())
		others = sum([node.get_process_fragment() for node in self.dfg], Fragment())
		return this + others

def add_connection(dfg, source_node, sink_node, source_ep=None, sink_ep=None):
	if source_ep is None:
		source_eps = source_node.sources()
		assert(len(source_eps) == 1)
		source_ep = source_eps[0]
	if sink_ep is None:
		sink_eps = sink_node.sinks()
		assert(len(sink_eps) == 1)
		sink_ep = sink_eps[0]
	assert(isinstance(source_ep, Source))
	assert(isinstance(sink_ep, Sink))
	assert(source_ep in source_node.endpoints)
	assert(sink_ep in sink_node.endpoints)
	dfg.add_edge(source_node, sink_node, source=source_ep, sink=sink_ep)
