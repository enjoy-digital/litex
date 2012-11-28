from operator import itemgetter

from migen.fhdl.structure import *
from migen.fhdl import visit as fhdl

class FinalizeError(Exception):
	pass

class AbstractLoad:
	def __init__(self, target, source):
		self.target = target
		self.source = source
	
	def lower(self):
		if not self.target.finalized:
			raise FinalizeError
		return self.target.sel.eq(self.target.source_encoding[id(self.source)])

class LowerAbstractLoad(fhdl.NodeTransformer):
	def visit_unknown(self, node):
		if isinstance(node, AbstractLoad):
			return node.lower()
		else:
			return node

class ImplRegister:
	def __init__(self, name, nbits):
		self.name = name
		self.storage = Signal(BV(nbits), name=self.name)
		self.source_encoding = {}
		self.id_to_source = {}
		self.finalized = False
	
	def load(self, source):
		if id(source) not in self.source_encoding:
			self.source_encoding[id(source)] = len(self.source_encoding) + 1
			self.id_to_source[id(source)] = source
		return AbstractLoad(self, source)
	
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
		cases = [(v, self.storage.eq(self.id_to_source[k])) for k, v in items]
		sync = [Case(self.sel, *cases)]
		return Fragment(sync=sync)
