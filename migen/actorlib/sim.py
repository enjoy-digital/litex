from migen.fhdl.std import *
from migen.flow.actor import *
from migen.flow.transactions import *
from migen.util.misc import xdir

def _sim_multiread(sim, obj):
	if isinstance(obj, Signal):
		return sim.rd(obj)
	else:
		r = {}
		for k, v in xdir(obj, True):
			rd = _sim_multiread(sim, v)
			if isinstance(rd, int) or rd:
				r[k] = rd
		return r

def _sim_multiwrite(sim, obj, value):
	if isinstance(obj, Signal):
		sim.wr(obj, value)
	else:
		for k, v in value.items():
			_sim_multiwrite(sim, getattr(obj, k), v)

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

	def _process_transactions(self, selfp):
		completed = set()
		for token in self.active:
			ep = getattr(self.actor, token.endpoint)
			if isinstance(ep, Sink):
				if selfp.simulator.rd(ep.ack) and selfp.simulator.rd(ep.stb):
					token.value = _sim_multiread(selfp.simulator, ep.payload)
					completed.add(token)
					selfp.simulator.wr(ep.ack, 0)
			elif isinstance(ep, Source):
				if selfp.simulator.rd(ep.ack) and selfp.simulator.rd(ep.stb):
					completed.add(token)
					selfp.simulator.wr(ep.stb, 0)
			else:
				raise TypeError
		self.active -= completed
		if not self.active:
			self.busy = True

	def _update_control_signals(self, selfp):
		for token in self.active:
			ep = getattr(self.actor, token.endpoint)
			if isinstance(ep, Sink):
				selfp.simulator.wr(ep.ack, 1)
			elif isinstance(ep, Source):
				_sim_multiwrite(selfp.simulator, ep.payload, token.value)
				selfp.simulator.wr(ep.stb, 1)
			else:
				raise TypeError

	def _next_transactions(self):
		try:
			transactions = next(self.generator)
		except StopIteration:
			self.busy = False
			self.done = True
			raise StopSimulation
		if isinstance(transactions, Token):
			self.active = {transactions}
		elif isinstance(transactions, (tuple, list, set)):
			self.active = set(transactions)
		elif transactions is None:
			self.active = set()
		else:
			raise TypeError
		if self.active and all(transaction.idle_wait for transaction in self.active):
			self.busy = False

	def do_simulation(self, selfp):
		if self.active:
			self._process_transactions(selfp)
		if not self.active:
			self._next_transactions()
			self._update_control_signals(selfp)
	do_simulation.passive = True

class SimActor(Module):
	def __init__(self, generator):
		self.busy = Signal()
		self.submodules.token_exchanger = TokenExchanger(generator, self)
	
	def do_simulation(self, selfp):
		selfp.busy = self.token_exchanger.busy
	do_simulation.passive = True

def _dumper_gen(prefix):
	while True:
		t = Token("result")
		yield t
		if len(t.value) > 1:
			s = str(t.value)
		else:
			s = str(list(t.value.values())[0])
		print(prefix + s)

class Dumper(SimActor):
	def __init__(self, layout, prefix=""):
		self.result = Sink(layout)
		SimActor.__init__(self, _dumper_gen(prefix))
