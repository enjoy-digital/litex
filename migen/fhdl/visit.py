from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _ArrayProxy

class NodeVisitor:
	def visit(self, node):
		if isinstance(node, Constant):
			self.visit_Constant(node)
		elif isinstance(node, Signal):
			self.visit_Signal(node)
		elif isinstance(node, _Operator):
			self.visit_Operator(node)
		elif isinstance(node, _Slice):
			self.visit_Slice(node)
		elif isinstance(node, Cat):
			self.visit_Cat(node)
		elif isinstance(node, Replicate):
			self.visit_Replicate(node)
		elif isinstance(node, _Assign):
			self.visit_Assign(node)
		elif isinstance(node, If):
			self.visit_If(node)
		elif isinstance(node, Case):
			self.visit_Case(node)
		elif isinstance(node, Fragment):
			self.visit_Fragment(node)
		elif isinstance(node, list):
			self.visit_statements(node)
		elif isinstance(node, dict):
			self.visit_clock_domains(node)
		elif isinstance(node, _ArrayProxy):
			self.visit_ArrayProxy(node)
		elif node is not None:
			self.visit_unknown(node)
	
	def visit_Constant(node):
		pass
	
	def visit_Signal(node):
		pass
	
	def visit_Operator(node):
		for o in node.operands:
			self.visit(o)
	
	def visit_Slice(node):
		self.visit(node.value)
	
	def visit_Cat(node):
		for e in node.l:
			self.visit(e)
	
	def visit_Replicate(node):
		self.visit(node.v)
	
	def visit_Assign(node):
		self.visit(node.l)
		self.visit(node.r)
	
	def visit_If(node):
		self.visit(node.cond)
		self.visit(node.t)
		self.visit(node.f)
	
	def visit_Case(node):
		self.visit(node.test)
		for v, statements in node.cases:
			self.visit(statements)
		self.visit(node.default)
	
	def visit_Fragment(node):
		self.visit(node.comb)
		self.visit(node.sync)
	
	def visit_statements(node):
		for statement in node:
			self.visit(statement)
	
	def visit_clock_domains(node):
		for clockname, statements in node.items():
			self.visit(statements)
	
	def visit_ArrayProxy(node):
		for choice in node.choices:
			self.visit(choice)
		self.visit(node.key)
	
	def visit_unknown(node):
		pass

class NodeTransformer:
	def visit(self, node):
		if isinstance(node, Constant):
			return self.visit_Constant(node)
		elif isinstance(node, Signal):
			return self.visit_Signal(node)
		elif isinstance(node, _Operator):
			return self.visit_Operator(node)
		elif isinstance(node, _Slice):
			return self.visit_Slice(node)
		elif isinstance(node, Cat):
			return self.visit_Cat(node)
		elif isinstance(node, Replicate):
			return self.visit_Replicate(node)
		elif isinstance(node, _Assign):
			return self.visit_Assign(node)
		elif isinstance(node, If):
			return self.visit_If(node)
		elif isinstance(node, Case):
			return self.visit_Case(node)
		elif isinstance(node, Fragment):
			return self.visit_Fragment(node)
		elif isinstance(node, list):
			return self.visit_statements(node)
		elif isinstance(node, dict):
			return self.visit_clock_domains(node)
		elif isinstance(node, _ArrayProxy):
			return self.visit_ArrayProxy(node)
		elif node is not None:
			return self.visit_unknown(node)
		else:
			return None
	
	def visit_Constant(node):
		return node
	
	def visit_Signal(node):
		return node
	
	def visit_Operator(node):
		node.operands = [self.visit(o) for o in node.operands]
		return node
	
	def visit_Slice(node):
		node.value = self.visit(node.value)
		return node
	
	def visit_Cat(node):
		node.l = [self.visit(e) for e in node.l]
		return node
	
	def visit_Replicate(node):
		node.v = self.visit(node.v)
		return node
	
	def visit_Assign(node):
		node.l = self.visit(node.l)
		node.r = self.visit(node.r)
		return node
	
	def visit_If(node):
		node.cond = self.visit(node.cond)
		node.t = self.visit(node.t)
		node.f = self.visit(node.f)
		return node
	
	def visit_Case(node):
		node.test = self.visit(node.test)
		node.cases = [(v, self.visit(statements)) for v, statements in node.cases]
		node.default = self.visit(node.default)
		return node
	
	def visit_Fragment(node):
		node.comb = self.visit(node.comb)
		node.sync = self.visit(node.sync)
		return node
	
	def visit_statements(node):
		return [self.visit(statement) for statement in node]
	
	def visit_clock_domains(node):
		return dict((clockname, self.visit(statements)) for clockname, statements in node.items())
	
	def visit_ArrayProxy(node):
		node.choices = [self.visit(choice) for choice in node.choices]
		node.key = self.visit(node.key)
		return node
	
	def visit_unknown(node):
		return node
