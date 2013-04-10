from migen.flow.hooks import *

class EndpointReporter(EndpointSimHook):
	def __init__(self, endpoint):
		EndpointSimHook.__init__(self, endpoint)
		self.reset()
	
	def reset(self):
		self.inactive = 0
		self.ack = 0
		self.nack = 0
	
	# Total number of cycles per token (inverse token rate)
	def cpt(self):
		return (self.inactive + self.nack + self.ack)/self.ack
	
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
	
	def on_ack(self):
		self.ack += 1
	
	def on_nack(self):
		self.nack += 1
		
	def on_inactive(self):
		self.inactive += 1

class DFGReporter(DFGHook):
	def __init__(self, dfg):
		DFGHook.__init__(self, dfg, lambda u, ep, v: EndpointReporter(getattr(u, ep)))

	def get_edge_labels(self):
		d = dict()
		for (u, v), eps in self.nodepair_to_ep.items():
			if len(eps) == 1:
				d[(u, v)] = list(eps.values())[0].report_str()
			else:
				d[(u, v)] = "\n".join(ep + ":\n" + reporter.report_str()
					for ep, reporter in eps)
		return d
