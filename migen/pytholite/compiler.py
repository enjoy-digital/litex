import inspect
import ast
from operator import itemgetter

from migen.fhdl.structure import *
from migen.fhdl import visit as fhdl
from migen.corelogic.fsm import FSM
from migen.pytholite import transel

class FinalizeError(Exception):
	pass

class _AbstractLoad:
	def __init__(self, target, source):
		self.target = target
		self.source = source
	
	def lower(self):
		if not self.target.finalized:
			raise FinalizeError
		return self.target.sel.eq(self.target.source_encoding[self.source])

class _LowerAbstractLoad(fhdl.NodeTransformer):
	def visit_unknown(self, node):
		if isinstance(node, _AbstractLoad):
			return node.lower()
		else:
			return node

class _Register:
	def __init__(self, name, nbits):
		self.name = name
		self.storage = Signal(BV(nbits), name=self.name)
		self.source_encoding = {}
		self.finalized = False
	
	def load(self, source):
		if source not in self.source_encoding:
			self.source_encoding[source] = len(self.source_encoding) + 1
		return _AbstractLoad(self, source)
	
	def finalize(self):
		if self.finalized:
			raise FinalizeError
		self.sel = Signal(BV(bits_for(len(self.source_encoding) + 1)), name="pl_regsel_"+self.name)
		self.finalized = True
	
	def get_fragment(self):
		if not self.finalized:
			raise FinalizeError
		# do nothing when sel == 0
		items = sorted(self.source_encoding.items(), key=itemgetter(1))
		cases = [(Constant(v, self.sel.bv),
			self.storage.eq(k)) for k, v in items]
		sync = [Case(self.sel, *cases)]
		return Fragment(sync=sync)

class _SymbolStack:
	def __init__(self):
		self.stack = []
	
	def push(self, init={}):
		self.stack.append(init)
	
	def pop(self):
		return self.stack.pop()
	
	def __setitem__(self, key, value):
		self.stack[-1][key] = value
	
	def __getitem__(self, key):
		for frame in reversed(self.stack):
			try:
				return frame[key]
			except KeyError:
				pass
		raise KeyError
		
class _AbstractNextState:
	def __init__(self, target_state):
		self.target_state = target_state

class _Compiler:
	def __init__(self, symdict, registers):
		self.symdict = _SymbolStack()
		self.symdict.push(symdict)
		self.registers = registers
		self.targetname = ""
	
	def visit_top(self, node):
		if isinstance(node, ast.Module) \
		  and len(node.body) == 1 \
		  and isinstance(node.body[0], ast.FunctionDef):
			states, exit_states = self.visit_block(node.body[0].body)
			return states
		else:
			raise NotImplementedError
	
	# blocks and statements
	def visit_block(self, statements):
		states = []
		exit_states = []
		for statement in statements:
			n_states, n_exit_states = self.visit_statement(statement)
			if n_states:
				states += n_states
				for exit_state in exit_states:
					exit_state.insert(0, _AbstractNextState(n_states[0]))
				exit_states = n_exit_states
		return states, exit_states
	
	# entry state is first state returned
	def visit_statement(self, statement):
		states = []
		exit_states = []
		if isinstance(statement, ast.Assign):
			op = self.visit_assign(statement)
			if op:
				states.append(op)
				exit_states.append(op)
		elif isinstance(statement, ast.If):
			test = self.visit_expr(statement.test)
			states_t, exit_states_t = self.visit_block(statement.body)
			states_f, exit_states_f  = self.visit_block(statement.orelse)
			
			test_state_stmt = If(test, _AbstractNextState(states_t[0]))
			test_state = [test_state_stmt]
			if states_f:
				test_state_stmt.Else(_AbstractNextState(states_f[0]))
			else:
				exit_states.append(test_state)
			
			states.append(test_state)
			states += states_t + states_f
			exit_states += exit_states_t + exit_states_f
		else:
			raise NotImplementedError
		return states, exit_states
	
	def visit_assign(self, node):
		if isinstance(node.targets[0], ast.Name):
			self.targetname = node.targets[0].id
		value = self.visit_expr(node.value, True)
		self.targetname = ""
		
		if isinstance(value, _Register):
			self.registers.append(value)
			for target in node.targets:
				if isinstance(target, ast.Name):
					self.symdict[target.id] = value
				else:
					raise NotImplementedError
			return []
		elif isinstance(value, Value):
			r = []
			for target in node.targets:
				if isinstance(target, ast.Attribute) and target.attr == "store":
					treg = target.value
					if isinstance(treg, ast.Name):
						r.append(self.symdict[treg.id].load(value))
					else:
						raise NotImplementedError
				else:
					raise NotImplementedError
			return r
		else:
			raise NotImplementedError
	
	# expressions
	def visit_expr(self, node, allow_call=False):
		if isinstance(node, ast.Call):
			if allow_call:
				return self.visit_expr_call(node)
			else:
				raise NotImplementedError
		elif isinstance(node, ast.BinOp):
			return self.visit_expr_binop(node)
		elif isinstance(node, ast.Compare):
			return self.visit_expr_compare(node)
		elif isinstance(node, ast.Name):
			return self.visit_expr_name(node)
		elif isinstance(node, ast.Num):
			return self.visit_expr_num(node)
		else:
			raise NotImplementedError
	
	def visit_expr_call(self, node):
		if isinstance(node.func, ast.Name):
			callee = self.symdict[node.func.id]
		else:
			raise NotImplementedError
		if callee == transel.Register:
			if len(node.args) != 1:
				raise TypeError("Register() takes exactly 1 argument")
			nbits = ast.literal_eval(node.args[0])
			return _Register(self.targetname, nbits)
		else:
			raise NotImplementedError
	
	def visit_expr_binop(self, node):
		left = self.visit_expr(node.left)
		right = self.visit_expr(node.right)
		if isinstance(node.op, ast.Add):
			return left + right
		elif isinstance(node.op, ast.Sub):
			return left - right
		elif isinstance(node.op, ast.Mult):
			return left * right
		elif isinstance(node.op, ast.LShift):
			return left << right
		elif isinstance(node.op, ast.RShift):
			return left >> right
		elif isinstance(node.op, ast.BitOr):
			return left | right
		elif isinstance(node.op, ast.BitXor):
			return left ^ right
		elif isinstance(node.op, ast.BitAnd):
			return left & right
		else:
			raise NotImplementedError
	
	def visit_expr_compare(self, node):
		test = self.visit_expr(node.left)
		r = None
		for op, rcomparator in zip(node.ops, node.comparators):
			comparator = self.visit_expr(rcomparator)
			if isinstance(op, ast.Eq):
				comparison = test == comparator
			elif isinstance(op, ast.NotEq):
				comparison = test != comparator
			elif isinstance(op, ast.Lt):
				comparison = test < comparator
			elif isinstance(op, ast.LtE):
				comparison = test <= comparator
			elif isinstance(op, ast.Gt):
				comparison = test > comparator
			elif isinstance(op, ast.GtE):
				comparison = test >= comparator
			else:
				raise NotImplementedError
			if r is None:
				r = comparison
			else:
				r = r & comparison
			test = comparator
		return r
	
	def visit_expr_name(self, node):
		r = self.symdict[node.id]
		if isinstance(r, _Register):
			r = r.storage
		return r
	
	def visit_expr_num(self, node):
		return Constant(node.n)

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
		if isinstance(node, _AbstractNextState):
			index = _index_is(self.states, node.target_state)
			estate = getattr(self.fsm, self.stnames[index])
			return self.fsm.next_state(estate)
		else:
			return node

def _create_fsm(states):
	stnames = ["S" + str(i) for i in range(len(states))]
	fsm = FSM(*stnames)
	lans = _LowerAbstractNextState(fsm, states, stnames)
	for i, state in enumerate(states):
		actions = lans.visit(state)
		fsm.act(getattr(fsm, stnames[i]), *actions)
	return fsm

def make_pytholite(func):
	tree = ast.parse(inspect.getsource(func))
	symdict = func.__globals__.copy()
	registers = []
	
	print("ast:")
	print(ast.dump(tree))
	
	states = _Compiler(symdict, registers).visit_top(tree)
	
	print("compilation result:")
	print(states)
	
	regf = Fragment()
	for register in registers:
		register.finalize()
		regf += register.get_fragment()
	
	fsm = _create_fsm(states)
	fsmf = _LowerAbstractLoad().visit(fsm.get_fragment())
	
	return regf + fsmf

