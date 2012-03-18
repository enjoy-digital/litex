from migen.fhdl.structure import *

class FSM:
	def __init__(self, *states, delayed_enters=[]):
		nstates = len(states) + sum([d[2] for d in delayed_enters])
		
		self._state_bv = BV(bits_for(nstates-1))
		self._state = Signal(self._state_bv)
		self._next_state = Signal(self._state_bv)
		for n, state in enumerate(states):
			setattr(self, state, Constant(n, self._state_bv))
		self.actions = [[] for i in range(len(states))]
		
		for name, target, delay in delayed_enters:
			target_state = getattr(self, target)
			if delay:
				name_state = len(self.actions)
				setattr(self, name, Constant(name_state, self._state_bv))
				for i in range(delay-1):
					self.actions.append([self.next_state(Constant(name_state+i+1, self._state_bv))])
				self.actions.append([self.next_state(target_state)])
			else:
				# alias
				setattr(self, name, getattr(self, target_state))
	
	def reset_state(self, state):
		self._state.reset = state
	
	def next_state(self, state):
		return self._next_state.eq(state)
	
	def act(self, state, *statements):
		self.actions[state.n] += statements
	
	def get_fragment(self):
		cases = [[Constant(s, self._state_bv)] + a
			for s, a in enumerate(self.actions) if a]
		comb = [
			self._next_state.eq(self._state),
			Case(self._state, *cases)
		]
		sync = [self._state.eq(self._next_state)]
		return Fragment(comb, sync)
