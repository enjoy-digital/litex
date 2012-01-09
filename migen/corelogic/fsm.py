from migen.fhdl.structure import *

class FSM:
	def __init__(self, *states):
		self._state_bv = BV(bits_for(len(states)-1))
		self._state = Signal(self._state_bv)
		self._next_state = Signal(self._state_bv)
		for state, n in zip(states, range(len(states))):
			setattr(self, state, Constant(n, self._state_bv))
		self.actions = [[] for i in range(len(states))]
	
	def reset_state(self, state):
		self._state.reset = state
	
	def next_state(self, state):
		return self._next_state.eq(state)
	
	def act(self, state, *statements):
		self.actions[state.n] += statements
	
	def get_fragment(self):
		cases = [[Constant(s, self._state_bv)] + a
			for s, a in zip(range(len(self.actions)), self.actions) if a]
		comb = [
			self._next_state.eq(self._state),
			Case(self._state, *cases)
		]
		sync = [self._state.eq(self._next_state)]
		return Fragment(comb, sync)
