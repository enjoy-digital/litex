from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.flow.actor import *

class EndpointSimHook(Module):
	def __init__(self, endpoint):
		self.endpoint = endpoint
	
	def on_ack(self):
		pass
	
	def on_nack(self):
		pass
	
	def on_inactive(self):
		pass
	
	def do_simulation(self, s):
		if s.rd(self.endpoint.stb):
			if s.rd(self.endpoint.ack):
				self.on_ack()
			else:
				self.on_nack()
		else:
			self.on_inactive()

class DFGHook:
	def __init__(self, dfg, create):
		assert(not dfg.is_abstract())
		self.nodepair_to_ep = dict()
		for u, v, data in dfg.edges_iter(data=True):
			if (u, v) in self.nodepair_to_ep:
				ep_to_hook = self.nodepair_to_ep[(u, v)]
			else:
				ep_to_hook = dict()
				self.nodepair_to_ep[(u, v)] = ep_to_hook
			ep = data["source"]
			ep_to_hook[ep] = create(u, ep, v)
	
	def hooks_iter(self):
		for v1 in self.nodepair_to_ep.values():
			for v2 in v1.values():
				yield v2
	
	def get_fragment(self):
		return sum([h.get_fragment() for h in self.hooks_iter()], Fragment())
