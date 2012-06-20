from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.sim.generic import PureSimulable

class EndpointReporter(PureSimulable):
	def __init__(self, endpoint):
		self.endpoint = endpoint
		self.reset()
	
	def reset(self):
		self.inactive = 0
		self.ack = 0
		self.nack = 0
	
	# Total number of cycles per token (inverse token rate)
	def cpt(self):
		return (self.inactive + self.nack + 1)/self.ack
	
	# Inactivity cycles per token (slack)
	def ipt(self):
		return self.inactive/self.ack
	
	# NAK cycles per token (backpressure)
	def npt(self):
		return self.nack/self.ack
	
	def report_str(self):
		if self.ack:
			return "C/T={:.2f}\nI/T={:.2f}\nN/T={:.2f}".format(self.cpt(), self.ipt(), self.npt())
		else:
			return "N/A"
	
	def do_simulation(self, s):
		if s.rd(self.endpoint.stb):
			if s.rd(self.endpoint.ack):
				self.ack += 1
			else:
				self.nack += 1
		else:
			self.inactive += 1

class DFGReporter:
	def __init__(self, dfg):
		assert(not dfg.is_abstract())
		self.nodepair_to_ep = dict()
		for u, v, data in dfg.edges_iter(data=True):
			if (u, v) in self.nodepair_to_ep:
				ep_to_reporter = self.nodepair_to_ep[(u, v)]
			else:
				ep_to_reporter = dict()
				self.nodepair_to_ep[(u, v)] = ep_to_reporter
			ep = data["source"]
			ep_to_reporter[ep] = EndpointReporter(u.actor.endpoints[ep])
	
	def get_fragment(self):
		frag = Fragment()
		for v1 in self.nodepair_to_ep.values():
			for v2 in v1.values():
				frag += v2.get_fragment()
		return frag
	
	def get_edge_labels(self):
		d = dict()
		for (u, v), eps in self.nodepair_to_ep.items():
			if len(eps) == 1:
				d[(u, v)] = list(eps.values())[0].report_str()
			else:
				d[(u, v)] = "\n".join(ep + ":\n" + reporter.report_str()
					for ep, reporter in eps)
		return d
