import inspect
import ast
from operator import itemgetter

from migen.fhdl.structure import *
from migen.fhdl.structure import _Slice
from migen.fhdl import visit as fhdl
from migen.pytholite import transel
from migen.pytholite.io import make_io_object, gen_io
from migen.pytholite.fsm import *

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

def _is_name_used(node, name):
	for n in ast.walk(node):
		if isinstance(n, ast.Name) and n.id == name:
			return True
	return False

class _Compiler:
	def __init__(self, ioo, symdict, registers):
		self.ioo = ioo
		self.symdict = symdict
		self.registers = registers
	
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
		sa = StateAssembler()
		statements = iter(statements)
		statement = None
		while True:
			if statement is None:
				try:
					statement = next(statements)
				except StopIteration:
					return sa.ret()
			if isinstance(statement, ast.Assign):
				# visit_assign can recognize a I/O pattern, consume several
				# statements from the iterator and return the first statement
				# that is not part of the I/O pattern anymore.
				statement = self.visit_assign(sa, statement, statements)
			else:
				if isinstance(statement, ast.If):
					self.visit_if(sa, statement)
				elif isinstance(statement, ast.While):
					self.visit_while(sa, statement)
				elif isinstance(statement, ast.For):
					self.visit_for(sa, statement)
				elif isinstance(statement, ast.Expr):
					self.visit_expr_statement(sa, statement)
				else:
					raise NotImplementedError
				statement = None
	
	def visit_assign(self, sa, node, statements):
		if isinstance(node.value, ast.Call):
			try:
				value = self.visit_expr_call(node.value)
			except NotImplementedError:
				return self.visit_assign_special(sa, node, statements)
		else:
			value = self.visit_expr(node.value)
		if isinstance(value, Value):
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
			sa.assemble([r], [r])
		else:
			raise NotImplementedError
	
	def visit_assign_special(self, sa, node, statements):
		value = node.value
		assert(isinstance(value, ast.Call))
		if isinstance(value.func, ast.Name):
			callee = self.symdict[value.func.id]
		else:
			raise NotImplementedError
		
		if callee == transel.Register:
			if len(value.args) != 1:
				raise TypeError("Register() takes exactly 1 argument")
			nbits = ast.literal_eval(value.args[0])
			if isinstance(node.targets[0], ast.Name):
				targetname = node.targets[0].id
			else:
				targetname = "unk"
			reg = _Register(targetname, nbits)
			self.registers.append(reg)
			for target in node.targets:
				if isinstance(target, ast.Name):
					self.symdict[target.id] = reg
				else:
					raise NotImplementedError
		else:
			return self.visit_io_pattern(sa, node.targets, callee, value.args, statements)
	
	def visit_io_pattern(self, sa, targets, model, args, statements):
		# first statement is <modelname> = <model>(<args>)
		if len(targets) != 1 or not isinstance(targets[0], ast.Name):
			raise NotImplementedError("Unrecognized I/O pattern")
		modelname = targets[0].id
		if modelname in self.symdict:
			raise NotImplementedError("I/O model name is not free")
		
		# second statement must be yield <modelname>
		try:
			ystatement = next(statements)
		except StopIteration:
			raise NotImplementedError("Incomplete or fragmented I/O pattern")
		if not isinstance(ystatement, ast.Expr) \
		  or not isinstance(ystatement.value, ast.Yield) \
		  or not isinstance(ystatement.value.value, ast.Name) \
		  or ystatement.value.value.id != modelname:
			raise NotImplementedError("Unrecognized I/O pattern")
		
		# following optional statements are assignments to registers
		# with <modelname> used in expressions.
		from_model = []
		while True:
			try:
				fstatement = next(statements)
			except StopIteration:
				fstatement = None
			if not isinstance(fstatement, ast.Assign) \
			  or not _is_name_used(fstatement.value, modelname):
				break
			tregs = []
			for target in fstatement.targets:
				if isinstance(target, ast.Attribute) and target.attr == "store":
					if isinstance(target.value, ast.Name):
						tregs.append(self.symdict[target.value.id])
					else:
						raise NotImplementedError
				else:
					raise NotImplementedError
			from_model.append((tregs, fstatement.value))
		
		states, exit_states = gen_io(self, model, args, from_model)
		sa.assemble(states, exit_states)
		return fstatement
	
	def visit_if(self, sa, node):
		test = self.visit_expr(node.test)
		states_t, exit_states_t = self.visit_block(node.body)
		states_f, exit_states_f = self.visit_block(node.orelse)
		exit_states = exit_states_t + exit_states_f
		
		test_state_stmt = If(test, AbstractNextState(states_t[0]))
		test_state = [test_state_stmt]
		if states_f:
			test_state_stmt.Else(AbstractNextState(states_f[0]))
		else:
			exit_states.append(test_state)
		
		sa.assemble([test_state] + states_t + states_f,
			exit_states)
	
	def visit_while(self, sa, node):
		test = self.visit_expr(node.test)
		states_b, exit_states_b = self.visit_block(node.body)

		test_state = [If(test, AbstractNextState(states_b[0]))]
		for exit_state in exit_states_b:
			exit_state.insert(0, AbstractNextState(test_state))
		
		sa.assemble([test_state] + states_b, [test_state])
	
	def visit_for(self, sa, node):
		if not isinstance(node.target, ast.Name):
			raise NotImplementedError
		target = node.target.id
		if target in self.symdict:
			raise NotImplementedError("For loop target must use an available name")
		it = self.visit_iterator(node.iter)
		states = []
		last_exit_states = []
		for iteration in it:
			self.symdict[target] = iteration
			states_b, exit_states_b = self.visit_block(node.body)
			for exit_state in last_exit_states:
				exit_state.insert(0, AbstractNextState(states_b[0]))
			last_exit_states = exit_states_b
			states += states_b
		del self.symdict[target]
		sa.assemble(states, last_exit_states)
	
	def visit_iterator(self, node):
		if isinstance(node, ast.List):
			return ast.literal_eval(node)
		elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
			funcname = node.func.id
			args = map(ast.literal_eval, node.args)
			if funcname == "range":
				return range(*args)
			else:
				raise NotImplementedError
		else:
			raise NotImplementedError
	
	def visit_expr_statement(self, sa, node):
		if isinstance(node.value, ast.Yield):
			yvalue = node.value.value
			if not isinstance(yvalue, ast.Call) or not isinstance(yvalue.func, ast.Name):
				raise NotImplementedError("Unrecognized I/O pattern")
			callee = self.symdict[yvalue.func.id]
			states, exit_states = gen_io(self, callee, yvalue.args, [])
			sa.assemble(states, exit_states)
		else:
			raise NotImplementedError
	
	# expressions
	def visit_expr(self, node):
		if isinstance(node, ast.Call):
			return self.visit_expr_call(node)
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
		if callee == transel.bitslice:
			if len(node.args) != 2 and len(node.args) != 3:
				raise TypeError("bitslice() takes 2 or 3 arguments")
			val = self.visit_expr(node.args[0])
			low = ast.literal_eval(node.args[1])
			if len(node.args) == 3:
				up = ast.literal_eval(node.args[2])
			else:
				up = low + 1
			return _Slice(val, low, up)
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
		if node.id == "True":
			return Constant(1)
		if node.id == "False":
			return Constant(0)
		r = self.symdict[node.id]
		if isinstance(r, _Register):
			r = r.storage
		if isinstance(r, int):
			r = Constant(r)
		return r
	
	def visit_expr_num(self, node):
		return Constant(node.n)

def make_pytholite(func, **ioresources):
	ioo = make_io_object(**ioresources)
	
	tree = ast.parse(inspect.getsource(func))
	symdict = func.__globals__.copy()
	registers = []
	
	states = _Compiler(ioo, symdict, registers).visit_top(tree)
	
	regf = Fragment()
	for register in registers:
		register.finalize()
		regf += register.get_fragment()
	
	fsm = implement_fsm(states)
	fsmf = _LowerAbstractLoad().visit(fsm.get_fragment())
	
	ioo.fragment = regf + fsmf
	return ioo
