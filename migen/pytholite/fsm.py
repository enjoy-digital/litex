from migen.genlib.fsm import FSM, NextState

def id_next_state(l):
	return NextState(id(l))

# entry state is first state returned
class StateAssembler:
	def __init__(self):
		self.states = []
		self.exit_states = []
	
	def assemble(self, n_states, n_exit_states):
		self.states += n_states
		for exit_state in self.exit_states:
			exit_state.insert(0, id_next_state(n_states[0]))
		self.exit_states = n_exit_states
	
	def ret(self):
		return self.states, self.exit_states

def implement_fsm(states):
	fsm = FSM()
	for state in states:
		fsm.act(id(state), state)
	return fsm
