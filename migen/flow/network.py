from networkx import MultiDiGraph

from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.corelogic.misc import optree

# Graph nodes can be either:
#  (1) a reference to an existing actor
#  (2) an abstract (class, dictionary) pair meaning that the actor class should be
#      instantiated with the parameters from the dictionary.
#      This form is needed to enable actor duplication or sharing during elaboration.

class ActorNode:
	def __init__(self, actor_class, parameters=None):
		if isinstance(actor_class, type):
			self.actor_class = actor_class
			self.parameters = parameters
		else:
			self.actor = actor_class
		self.name = None
	
	def is_abstract(self):
		return hasattr(self, "actor_class")
		
	def instantiate(self):
		if self.is_abstract():
			self.actor = self.actor_class(**self.parameters)
			del self.actor_class
			del self.parameters
	
	def get_dict(self):
		if self.is_abstract():
			return self.parameters
		else:
			return self.actor.__dict__
	
	def __repr__(self):
		if self.is_abstract():
			r = "<abstract " + self.actor_class.__name__
			if self.name is not None:
				r += ": " + self.name
			r += ">"
		else:
			r = repr(self.actor)
		return r

class DataFlowGraph(MultiDiGraph):
	def __init__(self):
		self.elaborated = False
		super().__init__()
	
	def add_connection(self, source_node, sink_node,
	  source_ep=None, sink_ep=None,		# default: assume nodes have 1 source/sink and use that one
	  source_subr=None, sink_subr=None):	# default: use whole record
		if not isinstance(source_node, ActorNode):
			source_node = ActorNode(source_node)
		if not isinstance(sink_node, ActorNode):
			sink_node = ActorNode(sink_node)
		self.add_edge(source_node, sink_node,
			source=source_ep, sink=sink_ep,
			source_subr=source_subr, sink_subr=sink_subr)
	
	# Returns a dictionary
	#   source -> [sink1, ..., sinkn]
	# each element being as a (node, endpoint) pair.
	# NB: ignores subrecords.
	def _source_to_sinks(self):
		d = dict()
		for u, v, data in self.edges_iter(data=True):
			el_src = (u, data["source"])
			el_dst = (v, data["sink"])
			if el_src in d:
				d[el_src].append(el_dst)
			else:
				d[el_src] = [el_dst]
		return d
		
	# List sources that feed more than one sink.
	# NB: ignores subrecords.
	def _list_divergences(self):
		d = self._source_to_sinks()
		return dict((k, v) for k, v in d.items() if len(v) > 1)
	
	# A graph is abstract if any of these conditions is met:
	#  (1) A node is an abstract actor.
	#  (2) A subrecord is used.
	#  (3) A single source feeds more than one sink.
	# NB: It is not allowed for a single sink to be fed by more than one source.
	def is_abstract(self):
		return any(x.is_abstract() for x in self) \
			or any(d["source_subr"] is not None or d["sink_subr"] is not None
				for u, v, d in self.edges_iter(data=True)) \
			or self._list_divergences()
	
	def _eliminate_subrecords(self):
		pass # TODO
	
	def _eliminate_divergences(self):
		pass # TODO
	
	def _instantiate_actors(self):
		for actor in self:
			actor.instantiate()
		for u, v, d in self.edges_iter(data=True):
			if d["source"] is None:
				source_eps = u.actor.sources()
				assert(len(source_eps) == 1)
				d["source"] = source_eps[0]
			if d["sink"] is None:
				sink_eps = v.actor.sinks()
				assert(len(sink_eps) == 1)
				d["sink"] = sink_eps[0]
	
	# Elaboration turns an abstract DFG into a concrete one.
	#   Pass 1: eliminate subrecords by inserting Combinator/Splitter actors
	#   Pass 2: eliminate divergences by inserting Distributor actors
	#   Pass 3: run optimizer (e.g. share and duplicate actors)
	#   Pass 4: instantiate all abstract actors and explicit "None" endpoints
	def elaborate(self, optimizer=None):
		if self.elaborated:
			return
		self.elaborated = True
		
		self._eliminate_subrecords()
		self._eliminate_divergences()
		if optimizer is not None:
			optimizer(self)
		self._instantiate_actors()

class CompositeActor(Actor):
	def __init__(self, dfg):
		dfg.elaborate()
		self.dfg = dfg
		super().__init__()
	
	def get_fragment(self):
		comb = [self.busy.eq(optree("|", [node.actor.busy for node in self.dfg]))]
		fragment = Fragment(comb)
		for node in self.dfg:
			fragment += node.actor.get_fragment()
		for u, v, d in self.dfg.edges_iter(data=True):
			ep_src = u.actor.endpoints[d["source"]]
			ep_dst = v.actor.endpoints[d["sink"]]
			fragment += get_conn_fragment(ep_src, ep_dst)
		return fragment
