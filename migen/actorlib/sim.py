from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.sim.generic import PureSimulable

class Token:
	def __init__(self, endpoint, value=None):
		self.endpoint = endpoint
		self.value = value

# Generators yield None or a tuple of Tokens.
# Tokens for Sink endpoints are pulled and the "value" field filled in.
# Tokens for Source endpoints are pushed according to their "value" field.
#
# NB: the possibility to push several tokens at once is important to interact
# with actors that only accept a group of tokens when all of them are available.
class TokenExchanger(PureSimulable):
	def __init__(self, generator, actor):
		self.generator = generator
		self.actor = actor
		self.active = set()
		self.done = False

	def _process_transactions(self, s):
		completed = set()
		for token in self.active:
			ep = self.actor.endpoints[token.endpoint]
			if isinstance(ep, Sink):
				if s.rd(ep.ack):
					if s.rd(ep.stb):
						token.value = s.multiread(ep.token)
						completed.add(token)
						s.wr(ep.ack, 0)
				else:
					s.wr(ep.ack, 1)
			elif isinstance(ep, Source):
				if s.rd(ep.stb):
					if s.rd(ep.ack):
						completed.add(token)
						s.wr(ep.stb, 0)
				else:
					s.wr(ep.stb, 1)
					s.multiwrite(ep.token, token.value)
			else:
				raise TypeError
		self.active -= completed
	
	def _next_transactions(self):
		try:
			transactions = next(self.generator)
		except StopIteration:
			self.done = True
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
	
	def do_simulation(self, s):
		if not self.done:
			if not self.active:
				self._next_transactions()
			if self.active:
				self._process_transactions(s)

class SimActor(Actor):
	def __init__(self, generator, *endpoint_descriptions, **misc):
		super().__init__(*endpoint_descriptions, **misc)
		self.token_exchanger = TokenExchanger(generator, self)
	
	def get_fragment(self):
		return self.token_exchanger.get_fragment()

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
		super().__init__(dumper_gen(),
			("result", Sink, layout))
