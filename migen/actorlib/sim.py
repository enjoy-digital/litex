from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.flow.actor import *
from migen.flow.transactions import *

# Generators yield None or a tuple of Tokens.
# Tokens for Sink endpoints are pulled and the "value" field filled in.
# Tokens for Source endpoints are pushed according to their "value" field.
#
# NB: the possibility to push several tokens at once is important to interact
# with actors that only accept a group of tokens when all of them are available.
class TokenExchanger(Module):
	def __init__(self, generator, actor):
		self.generator = generator
		self.actor = actor
		self.active = set()
		self.busy = True
		self.done = False

	def _process_transactions(self, s):
		completed = set()
		for token in self.active:
			ep = self.actor.endpoints[token.endpoint]
			if isinstance(ep, Sink):
				if s.rd(ep.ack) and s.rd(ep.stb):
					token.value = s.multiread(ep.token)
					completed.add(token)
					s.wr(ep.ack, 0)
			elif isinstance(ep, Source):
				if s.rd(ep.ack) and s.rd(ep.stb):
					completed.add(token)
					s.wr(ep.stb, 0)
			else:
				raise TypeError
		self.active -= completed
		if not self.active:
			self.busy = True

	def _update_control_signals(self, s):
		for token in self.active:
			ep = self.actor.endpoints[token.endpoint]
			if isinstance(ep, Sink):
				s.wr(ep.ack, 1)
			elif isinstance(ep, Source):
				s.multiwrite(ep.token, token.value)
				s.wr(ep.stb, 1)
			else:
				raise TypeError

	def _next_transactions(self):
		try:
			transactions = next(self.generator)
		except StopIteration:
			self.done = True
			self.busy = False
			transactions = None
		if isinstance(transactions, Token):
			self.active = {transactions}
		elif isinstance(transactions, tuple) \
			or isinstance(transactions, list) \
			or isinstance(transactions, set):
			self.active = set(transactions)
		elif transactions is None:
			self.active = set()
		else:
			raise TypeError
		if self.active and all(transaction.idle_wait for transaction in self.active):
			self.busy = False

	def do_simulation(self, s):
		if not self.done:
			if self.active:
				self._process_transactions(s)
			if not self.active:
				self._next_transactions()
				self._update_control_signals(s)

	do_simulation.initialize = True

class SimActor(Actor):
	def __init__(self, generator, *endpoint_descriptions, **misc):
		Actor.__init__(self, *endpoint_descriptions, **misc)
		self.token_exchanger = TokenExchanger(generator, self)
	
	def update_busy(self, s):
		s.wr(self.busy, self.token_exchanger.busy)
	
	def get_fragment(self):
		return self.token_exchanger.get_fragment() + Fragment(sim=[self.update_busy])

class Dumper(SimActor):
	def __init__(self, layout, prefix=""):
		def dumper_gen():
			while True:
				t = Token("result")
				yield t
				if len(t.value) > 1:
					s = str(t.value)
				else:
					s = str(list(t.value.values())[0])
				print(prefix + s)
		SimActor.__init__(self, dumper_gen(),
			("result", Sink, layout))
