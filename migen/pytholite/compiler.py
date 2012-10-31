import inspect
import ast

from migen.fhdl.structure import *
from migen.pytholite import transel

class FinalizeError(Exception):
	pass

class _AbstractLoad:
	def __init__(self, target, source):
		self.target = target
		self.source = source

class _Register:
	def __init__(self, name, nbits):
		self.storage = Signal(BV(nbits), name=name)
		self.source_encoding = {}
		self.finalized = False
	
	def load(self, source):
		if source not in self.source_encoding:
			self.source_encoding[source] = len(self.source_encoding) + 1
		return _AbstractLoad(self, source)
	
	def finalize(self):
		if self.finalized:
			raise FinalizeError
		self.sel = Signal(BV(bits_for(len(self.source_encoding) + 1)))
		self.finalized = True
	
	def get_fragment(self):
		if not self.finalized:
			raise FinalizeError
		# do nothing when sel == 0
		cases = [(v, self.storage.eq(k)) for k, v in self.source_encoding.items()]
		sync = [Case(self.sel, *cases)]
		return Fragment(sync=sync)

class _AnonymousRegister:
	def __init__(self, nbits):
		self.nbits = nbits

class _CompileVisitor(ast.NodeVisitor):
	def __init__(self, symdict, registers):
		self.symdict = symdict
		self.registers = registers
	
	def visit_Assign(self, node):
		value = self.visit(node.value)
		if isinstance(value, _AnonymousRegister):
			if isinstance(node.targets[0], ast.Name):
				name = node.targets[0].id
			else:
				raise NotImplementedError
			value = _Register(name, value.nbits)
			self.registers.append(value)
			for target in node.targets:
				if isinstance(target, ast.Name):
					self.symdict[target.id] = value
				else:
					raise NotImplementedError
	
	def visit_Call(self, node):
		if isinstance(node.func, ast.Name):
			callee = self.symdict[node.func.id]
		else:
			raise NotImplementedError
		if callee == transel.Register:
			if len(node.args) != 1:
				raise TypeError("Register() takes exactly 1 argument")
			nbits = ast.literal_eval(node.args[0])
			return _AnonymousRegister(nbits)
		else:
			raise NotImplementedError
	
def make_pytholite(func):
	tree = ast.parse(inspect.getsource(func))
	symdict = func.__globals__.copy()
	registers = []
	
	cv = _CompileVisitor(symdict, registers)
	cv.visit(tree)
	
	print(registers)
	print(symdict)

	#print(ast.dump(tree))
