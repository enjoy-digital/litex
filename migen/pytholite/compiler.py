import inspect
import ast
from collections import OrderedDict

from migen.fhdl.structure import *
from migen.fhdl.visit import TransformModule
from migen.fhdl.specials import Memory
from migen.genlib.ioo import UnifiedIOObject
from migen.pytholite.reg import *
from migen.pytholite.expr import *
from migen.pytholite import transel
from migen.pytholite.io import gen_io
from migen.pytholite.util import *

def _is_name_used(node, name):
	for n in ast.walk(node):
		if isinstance(n, ast.Name) and n.id == name:
			return True
	return False

def _make_function_args_dict(undefined, symdict, args, defaults):
	d = OrderedDict()
	for argument in args:
		d[argument.arg] = undefined
	for default, argname in zip(defaults, reversed(list(d.keys()))):
		default_val = eval_ast(default, symdict)
		d[argname] = default_val
	return d

def _process_function_args(symdict, function_def, args, kwargs):
	defargs = function_def.args
	undefined = object()

	ad_positional = _make_function_args_dict(undefined, symdict, defargs.args, defargs.defaults)
	vararg_name = defargs.vararg
	kwarg_name = defargs.kwarg
	ad_kwonly = _make_function_args_dict(undefined, symdict, defargs.kwonlyargs, defargs.kw_defaults)

	# grab argument values
	current_argvalue = iter(args)
	try:
		for argname in ad_positional.keys():
			ad_positional[argname] = next(current_argvalue)
	except StopIteration:
		pass
	vararg = tuple(current_argvalue)

	kwarg = OrderedDict()
	for k, v in kwarg.items():
		if k in ad_positional:
			ad_positional[k] = v
		elif k in ad_kwonly:
			ad_kwonly[k] = v
		else:
			kwarg[k] = v

	# check
	undefined_pos = [k for k, v in ad_positional.items() if v is undefined]
	if undefined_pos:
		formatted = " and ".join("'" + k + "'" for k in undefined_pos)
		raise TypeError("Missing required positional arguments: " + formatted)
	if vararg and vararg_name is None:
		raise TypeError("Function takes {} positional arguments but {} were given".format(len(ad_positional),
			len(ad_positional) + len(vararg)))
	ad_kwonly = [k for k, v in ad_positional.items() if v is undefined]
	if undefined_pos:
		formatted = " and ".join("'" + k + "'" for k in undefined_pos)
		raise TypeError("Missing required keyword-only arguments: " + formatted)
	if kwarg and kwarg_name is None:
		formatted = " and ".join("'" + k + "'" for k in kwarg.keys())
		raise TypeError("Got unexpected keyword arguments: " + formatted)

	# update symdict
	symdict.update(ad_positional)
	if vararg_name is not None:
		symdict[vararg_name] = vararg
	symdict.update(ad_kwonly)
	if kwarg_name is not None:
		symdict[kwarg_name] = kwarg

class _Compiler:
	def __init__(self, ioo, symdict, registers):
		self.ioo = ioo
		self.symdict = symdict
		self.registers = registers
		self.ec = ExprCompiler(self.symdict)
	
	def visit_top(self, node, args, kwargs):
		if isinstance(node, ast.Module) \
		  and len(node.body) == 1 \
		  and isinstance(node.body[0], ast.FunctionDef):
			function_def = node.body[0]
			_process_function_args(self.symdict, function_def, args, kwargs)
			states, exit_states = self.visit_block(function_def.body)
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
		if isinstance(value, (int, bool, Value)):
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
			bits_sign = eval_ast(value.args[0], self.symdict)
			if isinstance(node.targets[0], ast.Name):
				targetname = node.targets[0].id
			else:
				targetname = "unk"
			reg = ImplRegister(targetname, bits_sign)
			self.registers.append(reg)
			for target in node.targets:
				if isinstance(target, ast.Name):
					self.symdict[target.id] = reg
				else:
					raise NotImplementedError
		else:
			return self.visit_io_pattern(sa, node.targets, callee, value.args, value.keywords, statements)
	
	def visit_io_pattern(self, sa, targets, model, args, keywords, statements):
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
		
		states, exit_states = gen_io(self, modelname, model, args, keywords, from_model)
		sa.assemble(states, exit_states)
		return fstatement
	
	def visit_if(self, sa, node):
		test = self.ec.visit_expr(node.test)
		states_t, exit_states_t = self.visit_block(node.body)
		states_f, exit_states_f = self.visit_block(node.orelse)
		exit_states = exit_states_t + exit_states_f
		
		test_state_stmt = If(test, id_next_state(states_t[0]))
		test_state = [test_state_stmt]
		if states_f:
			test_state_stmt.Else(id_next_state(states_f[0]))
		else:
			exit_states.append(test_state)
		
		sa.assemble([test_state] + states_t + states_f,
			exit_states)
	
	def visit_while(self, sa, node):
		test = self.ec.visit_expr(node.test)
		states_b, exit_states_b = self.visit_block(node.body)

		test_state = [If(test, id_next_state(states_b[0]))]
		for exit_state in exit_states_b:
			exit_state.insert(0, id_next_state(test_state))
		
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
				exit_state.insert(0, id_next_state(states_b[0]))
			last_exit_states = exit_states_b
			states += states_b
		del self.symdict[target]
		sa.assemble(states, last_exit_states)
	
	def visit_iterator(self, node):
		return eval_ast(node, self.symdict)

	def visit_expr_statement(self, sa, node):
		if isinstance(node.value, ast.Yield):
			yvalue = node.value.value
			if not isinstance(yvalue, ast.Call) or not isinstance(yvalue.func, ast.Name):
				raise NotImplementedError("Unrecognized I/O pattern")
			callee = self.symdict[yvalue.func.id]
			states, exit_states = gen_io(self, None, callee, yvalue.args, yvalue.keywords, [])
			sa.assemble(states, exit_states)
		else:
			raise NotImplementedError

class Pytholite(UnifiedIOObject):
	def __init__(self, func, *args, **kwargs):
		self.func = func
		self.args = args
		self.kwargs = kwargs

	def do_finalize(self):
		UnifiedIOObject.do_finalize(self)
		if self.get_dataflow():
			self.busy.reset = 1
		self.memory_ports = dict()
		for mem in self.__dict__.values():
			if isinstance(mem, Memory):
				port = mem.get_port(write_capable=True, we_granularity=8)
				self.specials += port
				self.memory_ports[mem] = port
		self._compile()

	def _compile(self):
		tree = ast.parse(inspect.getsource(self.func))
		symdict = self.func.__globals__.copy()
		registers = []
		
		states = _Compiler(self, symdict, registers).visit_top(tree, self.args, self.kwargs)
		
		for register in registers:
			if register.source_encoding:
				register.finalize()
				self.submodules += register
		
		fsm = implement_fsm(states)
		self.submodules += TransformModule(LowerAbstractLoad().visit, fsm)
