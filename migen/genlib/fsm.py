from collections import OrderedDict

from migen.fhdl.std import *
from migen.fhdl.module import FinalizeError
from migen.fhdl.visit import NodeTransformer

class AnonymousState:
	pass

# do not use namedtuple here as it inherits tuple
# and the latter is used elsewhere in FHDL
class NextState:
	def __init__(self, state):
		self.state = state

class _LowerNextState(NodeTransformer):
	def __init__(self, next_state_signal, encoding, aliases):
		self.next_state_signal = next_state_signal
		self.encoding = encoding
		self.aliases = aliases
		
	def visit_unknown(self, node):
		if isinstance(node, NextState):
			try:
				actual_state = self.aliases[node.state]
			except KeyError:
				actual_state = node.state
			return self.next_state_signal.eq(self.encoding[actual_state])
		else:
			return node

class FSM(Module):
	def __init__(self):
		self.actions = OrderedDict()
		self.state_aliases = dict()
		self.reset_state = None

	def act(self, state, *statements):
		if self.finalized:
			raise FinalizeError
		if state not in self.actions:
			self.actions[state] = []
		self.actions[state] += statements

	def delayed_enter(self, name, target, delay):
		if self.finalized:
			raise FinalizeError
		if delay:
			state = name
			for i in range(delay):
				if i == delay - 1:
					next_state = target
				else:
					next_state = AnonymousState()
				self.act(state, NextState(next_state))
				state = next_state
		else:
			self.state_aliases[name] = target
	
	def do_finalize(self):
		nstates = len(self.actions)

		self.encoding = dict((s, n) for n, s in enumerate(self.actions.keys()))
		self.state = Signal(max=nstates)
		self.next_state = Signal(max=nstates)

		lns = _LowerNextState(self.next_state, self.encoding, self.state_aliases)
		cases = dict((self.encoding[k], lns.visit(v)) for k, v in self.actions.items() if v)
		self.comb += [
			self.next_state.eq(self.state),
			Case(self.state, cases)
		]
		self.sync += self.state.eq(self.next_state)
