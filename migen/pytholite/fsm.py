from migen.fhdl import visit as fhdl
from migen.corelogic.fsm import FSM

class AbstractNextState:
	def __init__(self, target_state):
		self.target_state = target_state

# entry state is first state returned
class StateAssembler:
	def __init__(self):
		self.states = []
		self.exit_states = []
	
	def assemble(self, n_states, n_exit_states):
		self.states += n_states
		for exit_state in self.exit_states:
			exit_state.insert(0, AbstractNextState(n_states[0]))
		self.exit_states = n_exit_states
	
	def ret(self):
		return self.states, self.exit_states

# like list.index, but using "is" instead of comparison
def _index_is(l, x):
	for i, e in enumerate(l):
		if e is x:
			return i

class _LowerAbstractNextState(fhdl.NodeTransformer):
	def __init__(self, fsm, states, stnames):
		self.fsm = fsm
		self.states = states
		self.stnames = stnames
		
	def visit_unknown(self, node):
		if isinstance(node, AbstractNextState):
			index = _index_is(self.states, node.target_state)
			estate = getattr(self.fsm, self.stnames[index])
			return self.fsm.next_state(estate)
		else:
			return node

def implement_fsm(states):
	stnames = ["S" + str(i) for i in range(len(states))]
	fsm = FSM(*stnames)
	lans = _LowerAbstractNextState(fsm, states, stnames)
	for i, state in enumerate(states):
		actions = lans.visit(state)
		fsm.act(getattr(fsm, stnames[i]), *actions)
	return fsm
