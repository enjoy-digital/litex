from migen.fhdl.structure import *

class FSM:
	def __init__(self, *states, delayed_enters=[]):
		nstates = len(states) + sum([d[2] for d in delayed_enters])
		
		self._state = Signal(max=nstates)
		self._next_state = Signal(max=nstates)
		for n, state in enumerate(states):
			setattr(self, state, n)
		self.actions = [[] for i in range(len(states))]
		
		for name, target, delay in delayed_enters:
			target_state = getattr(self, target)
			if delay:
				name_state = len(self.actions)
				setattr(self, name, name_state)
				for i in range(delay-1):
					self.actions.append([self.next_state(name_state+i+1)])
				self.actions.append([self.next_state(target_state)])
			else:
				# alias
				setattr(self, name, getattr(self, target_state))
	
	def reset_state(self, state):
		self._state.reset = state
	
	def next_state(self, state):
		return self._next_state.eq(state)
	
	def act(self, state, *statements):
		self.actions[state] += statements
	
	def get_fragment(self):
		cases = dict((s, a) for s, a in enumerate(self.actions) if a)
		comb = [
			self._next_state.eq(self._state),
			Case(self._state, cases)
		]
		sync = [self._state.eq(self._next_state)]
		return Fragment(comb, sync)
