import inspect
import ast

from migen.fhdl.structure import *
from migen.fhdl.structure import _Slice
from migen.pytholite.reg import *
from migen.pytholite.expr import *
from migen.pytholite import transel
from migen.pytholite.io import make_io_object, gen_io
from migen.pytholite.fsm import *

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
		self.ec = ExprCompiler(self.symdict)
	
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
			is_special = False
			try:
				value = self.ec.visit_expr_call(node.value)
			except NotImplementedError:
				is_special = True
			if is_special:
				return self.visit_assign_special(sa, node, statements)
		else:
			value = self.ec.visit_expr(node.value)
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
			reg = ImplRegister(targetname, nbits)
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
			print(ast.dump(ystatement))
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
		test = self.ec.visit_expr(node.test)
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
		test = self.ec.visit_expr(node.test)
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
	fsmf = LowerAbstractLoad().visit(fsm.get_fragment())
	
	ioo.fragment = regf + fsmf
	return ioo
