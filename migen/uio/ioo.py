from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.transactions import *
from migen.actorlib.sim import TokenExchanger
from migen.bus import wishbone, memory
from migen.bus.transactions import *
from migen.uio.trampoline import Trampoline

class UnifiedIOObject(Actor):
	def __init__(self, dataflow=None, buses={}):
		if dataflow is not None:
			Actor.__init__(self, *dataflow)
		self.buses = buses
		self._memories = set(v for v in self.buses.values() if isinstance(v, Memory))
	
	def get_fragment(self):
		return Fragment(memories=self._memories)

(_WAIT_COMPLETE, _WAIT_POLL) = range(2)

class UnifiedIOSimulation(UnifiedIOObject):
	def __init__(self, generator, dataflow=None, buses={}):
		self.generator = Trampoline(generator)
		UnifiedIOObject.__init__(self, dataflow, buses)
		
		self.callers = []
		self.busname_to_caller_id = {}
		if dataflow is not None:
			self.callers.append(TokenExchanger(self.dispatch_g(0), self))
		for k, v in self.buses.items():
			caller_id = len(self.callers)
			self.busname_to_caller_id[k] = caller_id
			g = self.dispatch_g(caller_id)
			if isinstance(v, wishbone.Interface):
				caller = wishbone.Initiator(g, v)
			elif isinstance(v, Memory):
				caller = memory.Initiator(g, v)
			else:
				raise NotImplementedError
			self.callers.append(caller)
		
		self.dispatch_state = _WAIT_COMPLETE
		self.dispatch_caller = 0
		self.pending_transaction = None
	
	def identify_transaction(self, t):
		if isinstance(t, Token):
			return 0
		elif isinstance(t, TRead) or isinstance(t, TWrite):
			if t.busname is None:
				if len(self.busname_to_caller_id) != 1:
					raise TypeError
				else:
					return list(self.busname_to_caller_id.values())[0]
			else:
				return self.busname_to_caller_id[t.busname]
		else:
			raise TypeError
	
	def dispatch_g(self, caller_id):
		while True:
			if self.dispatch_state == _WAIT_COMPLETE and self.dispatch_caller == caller_id:
				transaction = next(self.generator)
				tr_cid = self.identify_transaction(transaction)
				self.dispatch_caller = tr_cid
				if tr_cid == caller_id:
					yield transaction
				else:
					self.pending_transaction = transaction
					self.dispatch_state = _WAIT_POLL
					yield None
			elif self.dispatch_state == _WAIT_POLL and self.dispatch_caller == caller_id:
				self.dispatch_state = _WAIT_COMPLETE
				yield self.pending_transaction
			else:
				yield None
	
	def get_fragment(self):
		f = UnifiedIOObject.get_fragment(self)
		return sum([c.get_fragment() for c in self.callers], f)
